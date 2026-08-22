import json
from django.test import TestCase, Client
from django.contrib.auth.models import User, Group
from cPlatformIO.models import Cluster, Node, Service, UserInfo, ApplicationInfo

class PlatformOpsContractTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_superuser("admin", "admin@platformops.io", "password")
        self.admin_group, _ = Group.objects.get_or_create(name="Admin")
        self.admin_group.user_set.add(self.admin_user)
        self.client.force_login(self.admin_user)

        self.app_ins = ApplicationInfo.objects.create(app_id="APP1001", app_name="PlatformOps Core")
        self.cluster = Cluster.objects.create(
            cluster_id="CLST1001", cluster_name="Test Cluster", repo_type="LocalVolume"
        )
        self.node = Node.objects.create(
            node_id="NODE1001", Cluster=self.cluster, node_name="Test Node", node_ip="127.0.0.1"
        )
        self.service = Service.objects.create(
            service_id="SERV1001", service_name="redis-core", service_type="redis",
            Node=self.node, Application=self.app_ins
        )

    def test_users_page_contract(self):
        response = self.client.get("/PlatformIO/Users/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "PlatformOps")

    def test_clusters_page_contract(self):
        response = self.client.get("/PlatformIO/ClusterView/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Cluster")

    def test_cluster_config_contract(self):
        response = self.client.post(
            "/PlatformIO/ClusterConfig/",
            data=json.dumps({"user-action": "open-cluster-config", "cluster_id": "CLST1001"}),
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

    def test_config_manager_contract(self):
        response = self.client.get("/PlatformIO/ConfigManager/")
        self.assertEqual(response.status_code, 200)

    def test_system_monitoring_contract(self):
        response = self.client.get("/PlatformIO/SystemMonitoring/")
        self.assertEqual(response.status_code, 200)

    def test_monitoring_contract(self):
        response = self.client.get("/PlatformIO/Monitoring/")
        self.assertEqual(response.status_code, 200)

    def test_diagnostics_contract(self):
        response = self.client.get("/PlatformIO/Diagnostics/")
        self.assertEqual(response.status_code, 200)
