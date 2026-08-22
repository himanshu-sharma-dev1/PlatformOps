import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch
import os
import sys

from requests import HTTPError

from scripts import observability_backfill
from scripts.prepare_cplatform_runtime import collect_contract_sources, render_alloy_config
from scripts.observability_utils import (
    ObservabilityError,
    derive_diagnostics_env_path,
    load_env_file,
    main_service_contract_records,
    parse_label_args,
    parse_log_timestamp,
    path_is_covered_by_volume,
    resolve_contract_value,
    resolve_host_volume_sources,
)


class ObservabilityUtilsTests(unittest.TestCase):
    def test_parse_log_timestamp_supports_iso8601(self):
        ts = parse_log_timestamp("2026-04-01T11:18:00Z hello")
        self.assertIsNotNone(ts)
        self.assertEqual(ts.isoformat(), "2026-04-01T11:18:00+00:00")

    def test_parse_log_timestamp_supports_standard_format(self):
        ts = parse_log_timestamp("2026-04-01 11:18:00,123 hello")
        self.assertIsNotNone(ts)
        self.assertEqual(ts.isoformat(), "2026-04-01T11:18:00.123000+00:00")

    def test_parse_label_args(self):
        labels = parse_label_args(["service_name=RabbitMQ", "source_type=file"])
        self.assertEqual(labels["service_name"], "RabbitMQ")
        self.assertEqual(labels["source_type"], "file")

    def test_resolve_contract_value(self):
        resolved = resolve_contract_value(
            "/{{ machine_volume }}/iktara/{{ service }}/logs",
            "/srv/service",
            "/srv/machine",
            "TrainingServer",
        )
        self.assertEqual(resolved, "/srv/machine/iktara/TrainingServer/logs")

    def test_derive_diagnostics_env_path_for_plain_deployment_env(self):
        self.assertEqual(
            derive_diagnostics_env_path(Path('/tmp/deployment.env')),
            Path('/tmp/diagnostics.env'),
        )

    def test_derive_diagnostics_env_path_for_suffixed_deployment_env(self):
        self.assertEqual(
            derive_diagnostics_env_path(Path('/tmp/deployment.validation.env')),
            Path('/tmp/diagnostics.validation.env'),
        )

    def test_load_env_file_strict_rejects_malformed_assignment(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'bad.env'
            path.write_text("key = value\n")
            with self.assertRaises(ObservabilityError):
                load_env_file(path, strict=True)

    def test_load_env_file_strict_allows_empty_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / 'good.env'
            path.write_text("EMPTY=\n")
            values = load_env_file(path, strict=True)
            self.assertEqual(values['EMPTY'], '')

    def test_resolve_host_volume_sources(self):
        volumes = [
            "/{{ service_volume }}/iktara/ans/logs:/iktara/app/logs",
            "/{{ machine_volume }}/iktara/Repository:/iktara/Repository",
        ]
        sources = resolve_host_volume_sources(volumes, "/srv/service", "/srv/machine", "ANS")
        self.assertEqual(
            sources,
            ["/srv/service/iktara/ans/logs", "/srv/machine/iktara/Repository"],
        )

    def test_path_is_covered_by_volume(self):
        self.assertTrue(path_is_covered_by_volume("/srv/service/logs", ["/srv/service/logs"]))
        self.assertTrue(path_is_covered_by_volume("/srv/service/logs/archive", ["/srv/service/logs"]))
        self.assertFalse(path_is_covered_by_volume("/srv/other/logs", ["/srv/service/logs"]))

    def test_main_service_contract_records_include_missing_main_contracts(self):
        config = {
            "services": {
                "Airflow": {
                    "Docker_Info": {
                        "Airflow-Web": {
                            "Image_Name": "iktaraai/services:Airflow",
                        }
                    }
                }
            }
        }
        self.assertEqual(main_service_contract_records(config), [("Airflow", {}, {})])


class PrepareRuntimeTests(unittest.TestCase):
    def test_collect_contract_sources_resolves_contract_paths(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            config_dir = repo_root / "cPlatform" / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "service_install.yaml").write_text(
                """
services:
  Demo:
    Docker_Info:
      Demo:
        Volumes:
          - "/{{ service_volume }}/iktara/demo/logs:/app/logs"
        Observability:
          file_logs:
            enabled: true
            paths:
              - "/{{ service_volume }}/iktara/demo/logs"
            loki_labels:
              service_name: "Demo"
              service_type: "Demo"
"""
            )

            sources = collect_contract_sources(
                repo_root,
                "/home/ubuntu/Backup_Platform",
                "validation",
                host_mount_prefix="/host-volume",
            )

        globs = {entry["id"]: entry["glob"] for entry in sources}
        self.assertEqual(globs["cplatform_logs"], "/host-volume/iktara/cPlatform/logs/*.log*")
        self.assertIn("/host-volume/iktara/demo/logs/*.log*", globs.values())

    def test_collect_contract_sources_rejects_unmounted_log_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            config_dir = repo_root / "cPlatform" / "config"
            config_dir.mkdir(parents=True, exist_ok=True)
            (config_dir / "service_install.yaml").write_text(
                """
services:
  Demo:
    Docker_Info:
      Demo:
        Volumes:
          - "/{{ service_volume }}/iktara/demo/config:/app/config"
        Observability:
          file_logs:
            enabled: true
            paths:
              - "/{{ service_volume }}/iktara/demo/logs"
            loki_labels:
              service_name: "Demo"
              service_type: "Demo"
"""
            )

            with self.assertRaises(SystemExit):
                render_alloy_config(
                    repo_root=repo_root,
                    machine_volume="/home/ubuntu/Backup_Platform",
                    node_id="NODE1001",
                    node_ip="127.0.0.1",
                    environment="validation",
                    host_mount_prefix="/host-volume",
                )

class ObservabilityBackfillTests(unittest.TestCase):
    def test_scan_log_bounds_ignores_future_and_unparseable_lines(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "seeded.log"
            path.write_text(
                "\n".join([
                    "not a timestamp",
                    "2000-01-01T00:00:00Z old line",
                    "2999-01-01T00:00:00Z future line",
                ])
            )
            earliest, latest, parsed_lines = observability_backfill.scan_log_bounds(path)

        self.assertEqual(parsed_lines, 1)
        self.assertEqual(earliest.isoformat(), "2000-01-01T00:00:00+00:00")
        self.assertEqual(latest.isoformat(), "2000-01-01T00:00:00+00:00")

    def test_probe_earliest_loki_timestamp_uses_bounded_range(self):
        response = Mock()
        response.status_code = 200
        response.json.return_value = {
            "data": {"result": [{"values": [["1711966680000000000", "line"]]}]}
        }
        response.raise_for_status = Mock()
        session = Mock()
        session.get.return_value = response
        start_at = datetime(2026, 4, 17, 5, 22, 0, tzinfo=timezone.utc)
        end_at = datetime(2026, 4, 17, 5, 24, 0, tzinfo=timezone.utc)

        earliest, probe_start, probe_end, probe_window = observability_backfill.probe_earliest_loki_timestamp(
            session,
            "http://loki:3100",
            {"service_name": "ASR", "service_type": "ASR", "source_type": "file"},
            start_at,
            end_at,
        )

        self.assertEqual(probe_window, "file_range")
        self.assertEqual(probe_start, start_at)
        self.assertEqual(probe_end, end_at)
        self.assertEqual(earliest.isoformat(), "2024-04-01T10:18:00+00:00")
        params = session.get.call_args.kwargs["params"]
        self.assertEqual(params["start"], "1776403320000000000")
        self.assertEqual(params["end"], "1776403440000000000")

    def test_probe_earliest_loki_timestamp_falls_back_after_range_limit(self):
        start_at = datetime(2026, 4, 1, 0, 0, 0, tzinfo=timezone.utc)
        end_at = datetime(2026, 4, 17, 5, 24, 0, tzinfo=timezone.utc)
        session = Mock()

        too_wide = Mock()
        too_wide.status_code = 400
        too_wide.text = "the query time range exceeds the limit"
        too_wide.raise_for_status.side_effect = HTTPError("range")

        success = Mock()
        success.status_code = 200
        success.text = ""
        success.raise_for_status = Mock()
        success.json.return_value = {
            "data": {"result": [{"values": [["1776403320000000000", "line"]]}]}
        }
        session.get.side_effect = [too_wide, success]

        class FixedDateTime(datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 4, 17, 5, 30, 0, tzinfo=tz or timezone.utc)

        with patch.object(observability_backfill, "datetime", FixedDateTime):
            earliest, probe_start, probe_end, probe_window = observability_backfill.probe_earliest_loki_timestamp(
                session,
                "http://loki:3100",
                {"service_name": "ASR", "service_type": "ASR", "source_type": "file"},
                start_at,
                end_at,
            )

        self.assertEqual(earliest.isoformat(), "2026-04-17T05:22:00+00:00")
        self.assertEqual(probe_window, "7d")
        self.assertEqual(probe_end.isoformat(), "2026-04-17T05:24:00+00:00")
        self.assertEqual(probe_start.isoformat(), "2026-04-10T05:30:00+00:00")
        first_params = session.get.call_args_list[0].kwargs["params"]
        second_params = session.get.call_args_list[1].kwargs["params"]
        self.assertNotEqual(first_params["start"], "0")
        self.assertEqual(second_params["start"], "1775799000000000000")


class ServiceDiagnosticsHistoryGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        repo_root = Path(__file__).resolve().parents[2]
        django_root = repo_root / "cPlatform"
        if str(django_root) not in sys.path:
            sys.path.insert(0, str(django_root))
        os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cPlatform.settings")
        try:
            import django
        except ModuleNotFoundError:
            raise unittest.SkipTest("django is not available in this test environment")

        django.setup()
        from cPlatformIO.src import ServiceDiagnostics

        cls.ServiceDiagnostics = ServiceDiagnostics

    def test_file_history_exists_uses_query_range_results(self):
        with patch.object(self.ServiceDiagnostics, "_query_loki_selector_range", return_value=[{"message": "line"}]):
            self.assertTrue(
                self.ServiceDiagnostics._file_history_exists(
                    {"service_name": "ASR", "service_type": "ASR", "source_type": "file"},
                    "7d",
                )
            )

    def test_file_history_exists_returns_false_when_no_lines_found(self):
        with patch.object(self.ServiceDiagnostics, "_query_loki_selector_range", return_value=[]):
            self.assertFalse(
                self.ServiceDiagnostics._file_history_exists(
                    {"service_name": "ASR", "service_type": "ASR", "source_type": "file"},
                    "7d",
                )
            )

if __name__ == "__main__":
    unittest.main()
