import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts.bootstrap_cplatform_host import (
    DEFAULT_PORTS,
    advertised_control_plane_ip,
    bootstrap_ports,
    build_health_checks,
    compose_ps,
    derive_remote_loki_ingest_url,
    ensure_network,
    REQUIRED_SOURCE_PATHS,
    copy_if_missing,
    patch_primary_node_ip,
    patch_remote_loki_ingest_url,
    validate_required_source_paths,
    validate_network,
    validate_static_ips,
)
from scripts.observability_utils import ObservabilityError


class BootstrapHostTests(unittest.TestCase):
    def test_copy_if_missing_copies_example_once(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / 'deployment.validation.env'
            example = Path(tmpdir) / 'deployment.validation.env.example'
            example.write_text('A=1\n')
            self.assertTrue(copy_if_missing(target, example))
            self.assertEqual(target.read_text(), 'A=1\n')
            self.assertFalse(copy_if_missing(target, example))

    def test_patch_primary_node_ip_replaces_placeholder(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / 'diagnostics.validation.env'
            env_path.write_text('CPLATFORM_PRIMARY_NODE_IP=127.0.0.1\nOTHER=1\n')
            patch_primary_node_ip(env_path, '54.183.53.93')
            self.assertIn('CPLATFORM_PRIMARY_NODE_IP=54.183.53.93\n', env_path.read_text())

    def test_advertised_control_plane_ip_prefers_explicit_primary_node_ip(self):
        self.assertEqual(
            advertised_control_plane_ip({'CPLATFORM_PRIMARY_NODE_IP': '54.183.53.93'}),
            '54.183.53.93',
        )

    def test_patch_remote_loki_ingest_url_replaces_internal_default(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / 'diagnostics.validation.env'
            env_path.write_text('CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL=http://loki:3100\n')
            patch_remote_loki_ingest_url(env_path, 'http://54.183.53.93:9011', host_port=9011)
            self.assertIn('CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL=http://54.183.53.93:9011\n', env_path.read_text())

    def test_patch_remote_loki_ingest_url_preserves_custom_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / 'diagnostics.validation.env'
            env_path.write_text('CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL=http://custom.example.com:9999\n')
            patch_remote_loki_ingest_url(env_path, 'http://54.183.53.93:9011', host_port=9011)
            self.assertIn('CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL=http://custom.example.com:9999\n', env_path.read_text())

    def test_patch_remote_loki_ingest_url_replaces_detected_host_ip_value(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            env_path = Path(tmpdir) / 'diagnostics.validation.env'
            env_path.write_text('CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL=http://172.31.15.237:9011\n')
            patch_remote_loki_ingest_url(
                env_path,
                'http://54.183.53.93:9011',
                detected_host_ip='172.31.15.237',
                host_port=9011,
            )
            self.assertIn('CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL=http://54.183.53.93:9011\n', env_path.read_text())

    def test_derive_remote_loki_ingest_url_prefers_explicit_value(self):
        self.assertEqual(
            derive_remote_loki_ingest_url(
                {'CPLATFORM_DIAGNOSTICS_LOKI_INGEST_URL': 'http://54.183.53.93:9001/loki'},
                '54.183.53.93',
                9011,
            ),
            'http://54.183.53.93:9001/loki',
        )

    def test_bootstrap_ports_returns_fixed_ports(self):
        ports = bootstrap_ports()
        self.assertIn(9011, ports)
        self.assertIn(80, ports)
        self.assertIn(DEFAULT_PORTS['glitchtip'], ports)

    def test_build_health_checks_use_fixed_ports(self):
        checks = build_health_checks()
        self.assertEqual(checks[0]['url'], 'http://127.0.0.1:9011/ready')
        self.assertEqual(checks[3]['url'], 'http://127.0.0.1:80/')

    @mock.patch('scripts.bootstrap_cplatform_host.subprocess.run')
    def test_compose_ps_accepts_ndjson_output(self, subprocess_run):
        subprocess_run.return_value = mock.Mock(
            returncode=0,
            stdout='{"Service":"cplatform","State":"running"}\n{"Service":"loki","State":"running"}\n',
            stderr='',
        )

        rows = compose_ps(Path('/tmp/docker-compose.yaml'))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]['Service'], 'cplatform')
        self.assertEqual(rows[1]['Service'], 'loki')

    def test_validate_static_ips_rejects_ip_outside_subnet(self):
        with self.assertRaises(ObservabilityError):
            validate_static_ips('180.75.0.0/24', ['10.0.0.2'])

    @mock.patch('scripts.bootstrap_cplatform_host.inspect_network')
    def test_validate_network_accepts_matching_compose_network(self, inspect_network):
        inspect_network.return_value = {
            'Labels': {'com.docker.compose.network': 'cplatform_iktara_cPlatform'},
            'IPAM': {'Config': [{'Subnet': '180.75.0.0/24', 'Gateway': '180.75.0.1'}]},
        }
        validate_network('cplatform_iktara_cPlatform', '180.75.0.0/24', '180.75.0.1')

    @mock.patch('scripts.bootstrap_cplatform_host.inspect_network')
    def test_validate_network_accepts_matching_unmanaged_network(self, inspect_network):
        inspect_network.return_value = {
            'Labels': {},
            'IPAM': {'Config': [{'Subnet': '180.75.0.0/24', 'Gateway': '180.75.0.1'}]},
        }
        validate_network('cplatform_iktara_cPlatform', '180.75.0.0/24', '180.75.0.1')

    @mock.patch('scripts.bootstrap_cplatform_host.inspect_network')
    def test_validate_network_rejects_mismatched_network_shape(self, inspect_network):
        inspect_network.return_value = {
            'Labels': {},
            'IPAM': {'Config': [{'Subnet': '172.19.0.0/24', 'Gateway': '172.19.0.1'}]},
        }
        with self.assertRaises(ObservabilityError):
            validate_network('cplatform_iktara_cPlatform', '180.75.0.0/24', '180.75.0.1')

    @mock.patch('scripts.bootstrap_cplatform_host.subprocess.run')
    @mock.patch('scripts.bootstrap_cplatform_host.inspect_network')
    def test_ensure_network_creates_missing_network(self, inspect_network, subprocess_run):
        inspect_network.return_value = None
        subprocess_run.return_value = mock.Mock(returncode=0, stdout='created', stderr='')

        ensure_network('cplatform_iktara_cPlatform', '180.75.0.0/24', '180.75.0.1')

        subprocess_run.assert_called_once_with(
            [
                'docker',
                'network',
                'create',
                '--driver',
                'bridge',
                '--subnet',
                '180.75.0.0/24',
                '--gateway',
                '180.75.0.1',
                'cplatform_iktara_cPlatform',
            ],
            capture_output=True,
            text=True,
        )

    @mock.patch('scripts.bootstrap_cplatform_host.subprocess.run')
    @mock.patch('scripts.bootstrap_cplatform_host.inspect_network')
    def test_ensure_network_validates_existing_network(self, inspect_network, subprocess_run):
        inspect_network.return_value = {
            'Labels': {},
            'IPAM': {'Config': [{'Subnet': '180.75.0.0/24', 'Gateway': '180.75.0.1'}]},
        }

        ensure_network('cplatform_iktara_cPlatform', '180.75.0.0/24', '180.75.0.1')

        subprocess_run.assert_not_called()

    def test_validate_required_source_paths_rejects_missing_modelstore(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            for relative_path in REQUIRED_SOURCE_PATHS:
                if relative_path == 'ModelStore':
                    continue
                (repo_root / relative_path).mkdir(parents=True, exist_ok=True)

            with self.assertRaises(SystemExit) as exc:
                validate_required_source_paths(repo_root)

            self.assertIn('ModelStore', str(exc.exception))

    def test_validate_required_source_paths_accepts_complete_tree(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            for relative_path in REQUIRED_SOURCE_PATHS:
                (repo_root / relative_path).mkdir(parents=True, exist_ok=True)

            validate_required_source_paths(repo_root)

if __name__ == '__main__':
    unittest.main()
