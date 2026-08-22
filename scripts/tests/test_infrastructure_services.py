import ast
import unittest
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVICE_CONFIG = REPO_ROOT / "PlatformOps/PlatformOpsIO/src/ServiceConfig.py"
SERVICE_INSTALL = REPO_ROOT / "PlatformOps/config/service_install.yaml"
PLATFORM_CONFIG = REPO_ROOT / "PlatformOps/config/PlatformOps_config.yaml"
NOC_PROMETHEUS = REPO_ROOT / "platform/docker/prometheus/noc_prometheus.yml"
INFRA_PLAYBOOK = REPO_ROOT / "platform/ansible/playbook/infrastructure_service_install_playbook.yaml"
SERVICE_INSTALL_PLAYBOOK = REPO_ROOT / "platform/ansible/playbook/service_install_playbook.yaml"
SERVICE_DELETE_PLAYBOOK = REPO_ROOT / "platform/ansible/playbook/service_delete_primary.yaml"
SERVICE_STATUS_SCRIPT = REPO_ROOT / "platform/ansible/service_status.py"
CONFIG_MANAGER_TEMPLATE = REPO_ROOT / "PlatformOps/templates_new/PlatformIO/08-config-manager.html"
CLUSTER_DETAIL_TEMPLATE = REPO_ROOT / "PlatformOps/templates_new/PlatformIO/04-cluster-detail.html"
CLUSTER_LIST_TEMPLATE = REPO_ROOT / "PlatformOps/templates_new/PlatformIO/02-clusters.html"
CONFIG_MANAGER_CSS = REPO_ROOT / "PlatformOps/static/css/configManager.css"
NAVBAR_TEMPLATE = REPO_ROOT / "PlatformOps/templates_new/navbar.html"
CLUSTER_DETAIL_JS = REPO_ROOT / "PlatformOps/static/javascript/clusterDetail.js"
VIEWS_FILE = REPO_ROOT / "PlatformOps/PlatformOpsIO/views.py"
ROOT_READ_PLAYBOOKS = [
    REPO_ROOT / "platform/ansible/playbook/service_file_logs_playbook.yml",
    REPO_ROOT / "platform/ansible/playbook/service_file_archive_playbook.yml",
    REPO_ROOT / "platform/ansible/playbook/service_file_archive_fetch_playbook.yml",
    REPO_ROOT / "platform/ansible/playbook/service_log_backfill_playbook.yml",
    REPO_ROOT / "platform/ansible/playbook/service_config_snapshot_playbook.yml",
    REPO_ROOT / "platform/ansible/playbook/service_config_apply_playbook.yml",
    REPO_ROOT / "platform/ansible/playbook/service_config_restore_playbook.yml",
]


def _load_service_config_constants():
    module = ast.parse(SERVICE_CONFIG.read_text())
    constants = {}
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id in {
                "INFRASTRUCTURE_SERVICE_CATALOG",
                "INFRASTRUCTURE_CONFIG_PATHS",
                "INFRASTRUCTURE_DISCOVERY_BLOCKED_MARKERS",
                "INFRASTRUCTURE_SERVICE_EQUIVALENTS",
                "SERVICE_INFRASTRUCTURE_DEPENDENCIES",
            }:
                constants[target.id] = ast.literal_eval(node.value)
    return constants


class InfrastructureServiceCatalogTests(unittest.TestCase):
    def setUp(self):
        self.constants = _load_service_config_constants()
        with SERVICE_INSTALL.open() as handle:
            self.services = yaml.safe_load(handle)["services"]

    def test_catalog_entries_point_to_existing_contracts(self):
        catalog = self.constants["INFRASTRUCTURE_SERVICE_CATALOG"]
        self.assertGreaterEqual(len(catalog), 10)

        for infra_type, entry in catalog.items():
            self.assertIn(entry["source_service"], self.services)
            if entry["source_service"] == "Airflow":
                self.assertIn(infra_type, {
                    "InfraAirflowPostgreSQL",
                    "InfraAirflowRedis",
                    "InfraAirflowScheduler",
                    "InfraAirflowWorker",
                    "InfraAirflowDagProcessor",
                    "InfraAirflowTriggerer",
                })
            self.assertIn(
                entry["source_role"],
                self.services[entry["source_service"]]["Docker_Info"],
            )

    def test_dependency_map_references_catalog_and_airflow_only_requires_db_helpers(self):
        catalog = self.constants["INFRASTRUCTURE_SERVICE_CATALOG"]
        dependencies = self.constants["SERVICE_INFRASTRUCTURE_DEPENDENCIES"]

        self.assertEqual(dependencies["Airflow"], ["InfraAirflowPostgreSQL", "InfraAirflowRedis"])
        self.assertIn("RAG", dependencies)
        self.assertIn("ANS", dependencies)
        self.assertIn("InfraPostgreSQLCore", dependencies["RAG"])
        self.assertIn("InfraRabbitMQ", dependencies["TrainingServer"])
        self.assertIn("InfraPrometheus", dependencies["RAG"])
        self.assertIn("InfraPrometheus", dependencies["ANS"])
        self.assertNotIn("InfraProcessExporter", dependencies["ANS"])

        for service_type, infra_types in dependencies.items():
            self.assertIn(service_type, self.services)
            for infra_type in infra_types:
                self.assertIn(infra_type, catalog)

    def test_infrastructure_playbook_conditionally_publishes_host_ports(self):
        playbook_text = INFRA_PLAYBOOK.read_text()
        self.assertIn("published_ports", playbook_text)
        self.assertIn("if expose_service | bool", playbook_text)
        self.assertIn("host_port | string", playbook_text)
        self.assertIn("infra_contract_b64", playbook_text)
        self.assertIn("Image_Tag_Includes_Version", playbook_text)

    def test_root_owned_log_and_config_playbooks_use_become(self):
        for playbook_path in ROOT_READ_PLAYBOOKS:
            with self.subTest(playbook=playbook_path.name):
                playbook_text = playbook_path.read_text()
                self.assertIn("become: true", playbook_text)

    def test_infrastructure_config_paths_are_explicit_safe_paths(self):
        catalog = self.constants["INFRASTRUCTURE_SERVICE_CATALOG"]
        config_paths = self.constants["INFRASTRUCTURE_CONFIG_PATHS"]

        for infra_type, config_path in config_paths.items():
            self.assertIn(infra_type, catalog)
            self.assertTrue(str(config_path).startswith("/"))

        self.assertIn("InfraPostgreSQLCore", config_paths)
        self.assertIn("InfraRabbitMQ", config_paths)
        self.assertIn("InfraRedisCore", config_paths)
        self.assertIn("InfraAirflowPostgreSQL", config_paths)
        self.assertIn("InfraAirflowRedis", config_paths)

    def test_redis_infrastructure_cards_mount_explicit_config_files(self):
        catalog = self.constants["INFRASTRUCTURE_SERVICE_CATALOG"]
        for infra_type in ["InfraRedisCore", "InfraAirflowRedis"]:
            entry = catalog[infra_type]
            contract = self.services[entry["source_service"]]["Docker_Info"][entry["source_role"]]
            self.assertIn("/usr/local/etc/redis/redis.conf", contract.get("Command", ""))
            self.assertTrue(contract.get("Config_Files"))
            self.assertTrue(any("/usr/local/etc/redis/redis.conf" in volume for volume in contract.get("Volumes", [])))
            file_logs = contract.get("Observability", {}).get("file_logs", {})
            self.assertTrue(file_logs.get("enabled"))
            self.assertTrue(file_logs.get("paths"))

        airflow_redis = self.services["Airflow"]["Docker_Info"]["redis"]
        airflow_postgres = self.services["Airflow"]["Docker_Info"]["PostgreSQL"]
        self.assertTrue(airflow_redis.get("Image_Tag_Includes_Version"))
        self.assertTrue(airflow_postgres.get("Image_Tag_Includes_Version"))

    def test_all_infrastructure_cards_declare_file_log_paths(self):
        catalog = self.constants["INFRASTRUCTURE_SERVICE_CATALOG"]
        for infra_type, entry in catalog.items():
            with self.subTest(infra_type=infra_type):
                contract = self.services[entry["source_service"]]["Docker_Info"][entry["source_role"]]
                file_logs = contract.get("Observability", {}).get("file_logs", {})
                self.assertTrue(file_logs.get("enabled"))
                self.assertTrue(file_logs.get("paths"))

    def test_airflow_helpers_use_static_node_scoped_container_names(self):
        playbook_text = SERVICE_INSTALL_PLAYBOOK.read_text()

        expected_names = [
            "node-{{ airflow_node_fragment }}-airflow-scheduler",
            "node-{{ airflow_node_fragment }}-airflow-worker",
            "node-{{ airflow_node_fragment }}-airflow-dagprocessor",
            "node-{{ airflow_node_fragment }}-airflow-triggerer",
            "node-{{ airflow_node_fragment }}-airflow-init",
        ]
        for expected_name in expected_names:
            self.assertIn(expected_name, playbook_text)

        self.assertNotIn("docker wait {{ service_id }}-AirflowInit", playbook_text)
        self.assertIn("docker wait {{ airflow_container_names['AirflowInit'] }}", playbook_text)
        self.assertIn("Wait for explicit Airflow infrastructure dependency ports", playbook_text)
        self.assertNotIn("Deploy Airflow dependency containers", playbook_text)

    def test_airflow_cleanup_and_init_status_are_supported(self):
        delete_text = SERVICE_DELETE_PLAYBOOK.read_text()
        status_text = SERVICE_STATUS_SCRIPT.read_text()

        self.assertIn("Delete bundled Airflow helper containers", delete_text)
        self.assertIn("node-{{ airflow_node_fragment }}-airflow-init", delete_text)
        self.assertNotIn("node-{{ airflow_node_fragment }}-airflow-postgresql", delete_text)
        self.assertNotIn("node-{{ airflow_node_fragment }}-airflow-redis", delete_text)
        self.assertIn('dep_info.get("name") == "AirflowInit"', status_text)
        self.assertIn('dep_info["satisfied"] = True', status_text)

    def test_main_service_deployments_run_dependency_preflight_including_airflow_db_helpers(self):
        service_config_text = SERVICE_CONFIG.read_text()

        self.assertIn('"Airflow": ["InfraAirflowPostgreSQL", "InfraAirflowRedis"]', service_config_text)
        self.assertIn('"InfraPrometheus"', service_config_text)
        self.assertIn("preflight = service_check_dependency_preflight(ser_ins)", service_config_text)
        self.assertIn('"MISSING_DEPENDENCIES"', service_config_text)

    def test_shared_prometheus_has_hidden_legacy_aliases(self):
        catalog = self.constants["INFRASTRUCTURE_SERVICE_CATALOG"]
        equivalents = self.constants["INFRASTRUCTURE_SERVICE_EQUIVALENTS"]

        self.assertIn("InfraPrometheus", catalog)
        self.assertEqual(catalog["InfraPrometheus"]["source_service"], "ANS")
        self.assertFalse(catalog["InfraPrometheusANS"].get("catalog_visible", True))
        self.assertFalse(catalog["InfraPrometheusRAG"].get("catalog_visible", True))
        self.assertEqual(
            equivalents["InfraPrometheus"],
            ["InfraPrometheus", "InfraPrometheusANS", "InfraPrometheusRAG"],
        )

    def test_process_exporter_contract_is_present_and_uses_fixed_ip(self):
        catalog = self.constants["INFRASTRUCTURE_SERVICE_CATALOG"]
        self.assertIn("InfraProcessExporter", catalog)
        entry = catalog["InfraProcessExporter"]
        contract = self.services[entry["source_service"]]["Docker_Info"][entry["source_role"]]

        self.assertEqual(entry["source_service"], "ANS")
        self.assertEqual(contract.get("Int_IP_Addr"), "180.75.0.62")
        self.assertEqual(contract.get("Int_Port"), 9256)
        self.assertTrue(contract.get("Privileged"))
        self.assertIn("/proc:/host/proc:ro", contract.get("Volumes", []))
        self.assertTrue(contract.get("Config_Files"))

    def test_kafka_exporter_contract_and_noc_prometheus_wiring_are_pinned(self):
        catalog = self.constants["INFRASTRUCTURE_SERVICE_CATALOG"]
        self.assertIn("InfraKafkaExporter", catalog)
        entry = catalog["InfraKafkaExporter"]
        contract = self.services[entry["source_service"]]["Docker_Info"][entry["source_role"]]

        self.assertEqual(entry["source_service"], "ANS")
        self.assertEqual(contract.get("Image_Name"), "danielqsj/kafka-exporter:v1.8.0")
        self.assertTrue(contract.get("Image_Tag_Includes_Version"))
        self.assertTrue(contract.get("Pull_Image"))
        self.assertEqual(contract.get("Int_IP_Addr"), "180.75.0.63")
        self.assertEqual(contract.get("Int_Port"), 9308)
        self.assertEqual(contract.get("Network_Name"), "platformops_network")
        self.assertEqual(contract.get("Default_Host_Port"), 9014)
        self.assertEqual(contract.get("Environment", {}).get("KAFKA_SERVER"), "180.75.0.31:9092")

        platform_config = yaml.safe_load(PLATFORM_CONFIG.read_text())
        self.assertEqual(
            platform_config["INFRA_SERVICE_GROUPNAME_MAP"]["InfraKafkaExporter"],
            "kafka_exporter",
        )

        prometheus = yaml.safe_load(NOC_PROMETHEUS.read_text())
        jobs = {job["job_name"]: job for job in prometheus["scrape_configs"]}
        self.assertEqual(jobs["nifi"]["metrics_path"], "/nifi-api/flow/metrics/prometheus")
        self.assertEqual(jobs["noc-kafka"]["metrics_path"], "/metrics")
        self.assertEqual(jobs["noc-kafka"]["static_configs"][0]["targets"], ["180.75.0.63:9308"])

        process_block = """  - job_name: process-exporter
    metrics_path: /metrics
    static_configs:
      - targets:
          - 180.75.0.62:9256
        labels:
          service: process-exporter
"""
        self.assertIn(process_block, NOC_PROMETHEUS.read_text())

    def test_discovery_block_list_covers_known_observability_and_migration_projects(self):
        blocked = self.constants["INFRASTRUCTURE_DISCOVERY_BLOCKED_MARKERS"]

        for marker in ["glitchtip", "signoz", "config-migration", "alloy", "otel", "loki"]:
            self.assertIn(marker, blocked)

    def test_infrastructure_discovery_uses_exact_ip_and_quarantine_flow(self):
        service_config_text = SERVICE_CONFIG.read_text()

        self.assertIn('return 0, "expected_ip_mismatch"', service_config_text)
        self.assertIn('adoption_status="quarantined"', service_config_text)
        self.assertIn('summary["quarantined"] += 1', service_config_text)
        self.assertIn('validation_error=reason', service_config_text)

    def test_service_id_allocator_skips_discovered_runtime_names(self):
        service_config_text = SERVICE_CONFIG.read_text()

        self.assertIn("def _allocate_service_id", service_config_text)
        self.assertIn("candidate not in reserved_runtime_names", service_config_text)
        self.assertIn("_discovered_container_names(node_id", service_config_text)

    def test_config_manager_snapshot_rename_hooks_exist(self):
        service_config_text = SERVICE_CONFIG.read_text()
        template_text = CONFIG_MANAGER_TEMPLATE.read_text()
        views_text = VIEWS_FILE.read_text()

        self.assertIn("def service_rename_config_snapshot", service_config_text)
        self.assertIn("def _apply_config_snapshot_display_names", service_config_text)
        self.assertIn("display_name", service_config_text)
        self.assertIn("rename_checkpoint", views_text)
        self.assertIn("rename-snapshot-btn", template_text)
        self.assertIn("snapshotDisplayName", template_text)

    def test_cluster_detail_uses_themed_modals_for_dependency_and_node_blockers(self):
        template_text = CLUSTER_DETAIL_TEMPLATE.read_text()
        script_text = CLUSTER_DETAIL_JS.read_text()
        views_text = VIEWS_FILE.read_text()

        self.assertIn("css/ds.css", template_text)
        self.assertIn("javascript/theme.js", template_text)
        self.assertIn("actionBlockerModal", template_text)
        self.assertIn("svcInfraConfigFallback", template_text)
        self.assertIn("openActionBlockerModal", script_text)
        self.assertIn("startDependencyInstall", script_text)
        self.assertIn("renderServiceConfigFallback", script_text)
        self.assertNotIn("Deploy these infrastructure cards on", script_text)
        self.assertIn('"NODE_HAS_SERVICES"', views_text)

    def test_cluster_pages_use_navigation_and_themed_action_modals(self):
        cluster_text = CLUSTER_LIST_TEMPLATE.read_text()
        detail_text = CLUSTER_DETAIL_TEMPLATE.read_text()
        config_text = CONFIG_MANAGER_TEMPLATE.read_text()
        config_css = CONFIG_MANAGER_CSS.read_text()
        navbar_text = NAVBAR_TEMPLATE.read_text()
        script_text = CLUSTER_DETAIL_JS.read_text()
        views_text = VIEWS_FILE.read_text()

        self.assertIn("breadcrumb_items", navbar_text)
        self.assertIn("openDeleteClusterModal", cluster_text)
        self.assertIn("clusterActionModal", cluster_text)
        self.assertIn("delete_cluster", cluster_text)
        self.assertIn("cmConfirmModal", config_text)
        self.assertIn("openConfirmModal", config_text)
        self.assertIn("cm-modal", config_css)
        self.assertIn("breadcrumb_items", views_text)

        for text in (cluster_text, detail_text, config_text, script_text):
            self.assertNotIn("alert(", text)
            self.assertNotIn("confirm(", text)


if __name__ == "__main__":
    unittest.main()
