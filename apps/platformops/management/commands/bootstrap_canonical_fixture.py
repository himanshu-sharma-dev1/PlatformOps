import datetime
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group
from cPlatformIO.models import (
    ApplicationInfo, Cluster, Node, Service, UserInfo
)

class Command(BaseCommand):
    help = "Bootstraps the canonical redis-core fixture (CLST1001, NODE1001, redis-core) for acceptance testing."

    def handle(self, *args, **options):
        self.stdout.write("[Fixture] Initializing canonical fixture...")

        # 1. Base Application
        app_ins, created = ApplicationInfo.objects.get_or_create(
            app_id="APP1001",
            defaults={
                "app_name": "PlatformOps Core",
                "created_date": datetime.date.today(),
                "app_config": {"type": "Core_Infra", "version": "1.0.0"}
            }
        )
        self.stdout.write(f"  -> Application: {app_ins.app_name} (created: {created})")

        # 2. Canonical Cluster CLST1001
        cluster, created = Cluster.objects.get_or_create(
            cluster_id="CLST1001",
            defaults={
                "cluster_name": "Primary Core Cluster",
                "repo_type": "LocalVolume",
                "cluster_type": "Primary",
                "cluster_type_varient": "Standalone",
                "region": "ap-south-1 (Mumbai)",
                "environment": "Production",
                "description": "Canonical test cluster for PlatformOps acceptance validation"
            }
        )
        self.stdout.write(f"  -> Cluster: {cluster.cluster_id} - {cluster.cluster_name} (created: {created})")

        # 3. Canonical Node NODE1001
        node, created = Node.objects.get_or_create(
            node_id="NODE1001",
            Cluster=cluster,
            defaults={
                "node_name": "Core SRE Node",
                "node_ip": "127.0.0.1",
                "node_volume": "/tmp/platformops_node1001",
                "node_monitor_port": 9010,
                "node_launch_status": True,
                "auth_type": "Password",
                "username": "root",
                "password": "password",
                "gpu_status": "disabled",
                "node_provision_config": {
                    "cpu_cores": 8,
                    "ram_gb": 32,
                    "disk_gb": 500,
                    "os": "Ubuntu 22.04 LTS"
                }
            }
        )
        self.stdout.write(f"  -> Node: {node.node_id} - {node.node_name} (created: {created})")

        # 4. Canonical Managed Service redis-core
        service, created = Service.objects.get_or_create(
            service_id="SERV1001",
            defaults={
                "service_name": "redis-core",
                "service_type": "redis",
                "service_port": 6379,
                "service_volume": "/tmp/redis-core",
                "service_version": "7.2.0",
                "service_install": "DOCKER",
                "deploy_status": "DEPLOYED",
                "service_debug": "INFO",
                "Node": node,
                "Application": app_ins,
                "service_config": {
                    "maxmemory": "256mb",
                    "maxmemory-policy": "allkeys-lru",
                    "port": 6379,
                    "bind": "0.0.0.0",
                    "protected-mode": "no"
                }
            }
        )
        self.stdout.write(f"  -> Service: {service.service_id} - {service.service_name} (created: {created})")

        # 5. Core Roles and User
        admin_group, _ = Group.objects.get_or_create(name="Admin")
        op_group, _ = Group.objects.get_or_create(name="Operational")
        dev_group, _ = Group.objects.get_or_create(name="Developer")
        view_group, _ = Group.objects.get_or_create(name="Viewer")

        admin_user, _ = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@platformops.io", "is_staff": True, "is_superuser": True}
        )
        admin_user.set_password("admin")
        admin_user.save()
        admin_group.user_set.add(admin_user)

        user_info, created = UserInfo.objects.get_or_create(
            user_id="USR1001",
            defaults={
                "user_email": "admin@platformops.io",
                "user_name": "System Administrator",
                "user_role": "System_Admin",
                "user_number": "1234567890",
                "created_date": datetime.date.today(),
                "status": "active",
                "session_info": {"theme": "dark", "dashboard": "default"}
            }
        )
        self.stdout.write(f"  -> UserInfo: {user_info.user_name} ({user_info.user_email})")

        self.stdout.write(self.style.SUCCESS("[Fixture] Canonical fixture successfully bootstrapped!"))
