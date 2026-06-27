from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from platformops.catalog import rendered_contract, service_catalog  # noqa: E402
from platformops.db import Base, SessionLocal, engine, init_db  # noqa: E402
from platformops.models import Cluster, Node, ServiceInstance  # noqa: E402
from platformops.orchestrator import create_service_instance  # noqa: E402


def main() -> None:
    Base.metadata.drop_all(bind=engine)
    init_db()
    db = SessionLocal()
    try:
        cluster = db.query(Cluster).filter(Cluster.name == "local-lab").one_or_none()
        if cluster is None:
            cluster = Cluster(name="local-lab", region="local", environment="production")
            db.add(cluster)
            db.commit()
            db.refresh(cluster)

        node = db.query(Node).filter(Node.name == "local-mac").one_or_none()
        if node is None:
            node = Node(
                cluster_id=cluster.id,
                name="local-mac",
                host="localhost",
                ssh_user="local",
                environment="local",
                volume_root="/tmp/platformops",
                docker_network="platformops_prod_network",
                status="healthy",
            )
            db.add(node)
            db.commit()
            db.refresh(node)

        # Core active services in our actual environment
        core_services = {
            "postgres-core",
            "redis-core",
            "rabbitmq-core",
            "prometheus-core",
            "loki-core",
            "dtrain-controller",
            "dtrain-worker",
            "dtrain-tracker",
            "web-api",
        }

        always_running = {
            "postgres-core",
            "redis-core",
            "rabbitmq-core",
            "prometheus-core",
            "loki-core",
            "web-api",
        }

        real_containers = {
            "postgres-core": "platformops-postgres",
            "redis-core": "platformops-redis",
            "rabbitmq-core": "platformops-rabbitmq",
            "prometheus-core": "platformops-prometheus",
            "loki-core": "platformops-loki",
            "web-api": "platformops-web-api",
        }

        for service_key in core_services:
            service = create_service_instance(db, node=node, service_key=service_key)
            contract = rendered_contract(service_key, node_id=node.id, volume_root=node.volume_root)
            service.name = contract.get("display_name") or contract.get("name") or service_key
            service.kind = contract.get("kind", "app")
            service.container_name = real_containers.get(service_key, contract.get("container_name", f"node-{node.id}-{service_key}"))
            service.image = contract.get("image", "")
            service.config_json = json.dumps(contract)
            if service.service_key in always_running:
                service.status = "running"
            else:
                service.status = "created"
        db.commit()
    finally:
        db.close()

    print("Seeded PlatformOps demo data: cluster=local-lab nodes=local-mac")


if __name__ == "__main__":
    main()
