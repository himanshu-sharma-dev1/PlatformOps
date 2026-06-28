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
            cluster = Cluster(name="local-lab", region="local", environment="portfolio-demo")
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

        node_gpu = db.query(Node).filter(Node.name == "gpu-node").one_or_none()
        if node_gpu is None:
            node_gpu = Node(
                cluster_id=cluster.id,
                name="gpu-node",
                host="localhost",
                ssh_user="local",
                environment="local",
                volume_root="/tmp/platformops-gpu",
                docker_network="platformops_prod_network",
                status="healthy",
            )
            db.add(node_gpu)
            db.commit()
            db.refresh(node_gpu)

        node_edge = db.query(Node).filter(Node.name == "edge-node").one_or_none()
        if node_edge is None:
            node_edge = Node(
                cluster_id=cluster.id,
                name="edge-node",
                host="localhost",
                ssh_user="local",
                environment="local",
                volume_root="/tmp/platformops-edge",
                docker_network="platformops_prod_network",
                status="warning",
            )
            db.add(node_edge)
            db.commit()
            db.refresh(node_edge)

        catalog = service_catalog()
        for stale in db.query(ServiceInstance).filter(ServiceInstance.node_id == node.id).all():
            if stale.service_key not in catalog:
                db.delete(stale)
        db.commit()

        always_running = {
            "postgres-core",
            "redis-core",
            "rabbitmq-core",
            "clickhouse-core",
            "etcd-core",
            "minio-core",
            "milvus-core",
            "prometheus-core",
            "loki-core",
            "alloy-core",
            "node-exporter",
            "airflow-postgres",
            "airflow-redis",
            "dtrain-tracker",
        }

        for service_key in catalog:
            service = create_service_instance(db, node=node, service_key=service_key)
            contract = rendered_contract(service_key, node_id=node.id, volume_root=node.volume_root)
            service.name = contract.get("display_name") or contract.get("name") or service_key
            service.kind = contract.get("kind", "app")
            service.container_name = contract.get("container_name", f"node-{node.id}-{service_key}")
            service.image = contract.get("image", "")
            service.config_json = json.dumps(contract)
            if service.service_key in always_running:
                service.status = "running"
            elif service.service_key == "airflow-init":
                service.status = "success"
            elif service.status not in {"running", "success"}:
                service.status = "created"

        # Seed an observability stack on gpu-node to simulate multi-node topology
        observability_keys = {"prometheus-core", "loki-core", "alloy-core", "node-exporter", "dcgm-exporter"}
        for service_key in observability_keys:
            service = create_service_instance(db, node=node_gpu, service_key=service_key)
            contract = rendered_contract(service_key, node_id=node_gpu.id, volume_root=node_gpu.volume_root)
            service.name = contract.get("display_name") or contract.get("name") or service_key
            service.kind = contract.get("kind", "infrastructure")
            service.container_name = contract.get("container_name", f"node-{node_gpu.id}-{service_key}")
            service.image = contract.get("image", "")
            service.config_json = json.dumps(contract)
            service.status = "running"

        # Seed only shared data dependencies on edge-node as partially ready infra.
        shared_data_keys = {"postgres-core", "redis-core", "rabbitmq-core"}
        for service_key in shared_data_keys:
            service = create_service_instance(db, node=node_edge, service_key=service_key)
            contract = rendered_contract(service_key, node_id=node_edge.id, volume_root=node_edge.volume_root)
            service.name = contract.get("display_name") or contract.get("name") or service_key
            service.kind = contract.get("kind", "infrastructure")
            service.container_name = contract.get("container_name", f"node-{node_edge.id}-{service_key}")
            service.image = contract.get("image", "")
            service.config_json = json.dumps(contract)
            service.status = "running"
        db.commit()
    finally:
        db.close()

    print("Seeded PlatformOps demo data: cluster=local-lab nodes=local-mac,gpu-node,edge-node")


if __name__ == "__main__":
    main()
