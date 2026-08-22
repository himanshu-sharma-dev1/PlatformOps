from django.test import TestCase
from cPlatformIO.models import Cluster, Node, Service, UserInfo, ApplicationInfo, InviteToken
from cPlatformIO.src import UserMgmnt, ClusterConfig, NodeConfig, ServiceConfig

class PlatformOpsServiceLayerTests(TestCase):
    def setUp(self):
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

    def test_cluster_query(self):
        self.assertTrue(Cluster.objects.filter(cluster_id="CLST1001").exists())
        self.assertEqual(self.cluster.cluster_name, "Test Cluster")

    def test_node_query(self):
        self.assertTrue(Node.objects.filter(node_id="NODE1001").exists())
        self.assertEqual(self.node.Cluster, self.cluster)

    def test_service_query(self):
        self.assertTrue(Service.objects.filter(service_name="redis-core").exists())
        self.assertEqual(self.service.service_type, "redis")

    def test_user_creation_and_validation(self):
        user_info = UserInfo.objects.create(
            user_id="USR1002",
            user_email="operator@platformops.io",
            user_name="Operator User",
            user_role="Operational",
            created_date="2026-08-22",
            status="active"
        )
        self.assertEqual(user_info.user_email, "operator@platformops.io")
        self.assertEqual(user_info.status, "active")

    def test_invite_token_generation(self):
        invite = InviteToken.objects.create(
            user_email="invited@platformops.io",
            user_name="Invited User",
            user_role="Operational",
            permissions=["clusters", "diagnostics"]
        )
        self.assertIsNotNone(invite.token)
        self.assertFalse(invite.is_used)
        self.assertFalse(invite.is_revoked)
