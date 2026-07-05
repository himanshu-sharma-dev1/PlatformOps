from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..jobs import create_job, finish_job
from ..models import (
    Node,
    ServiceInstance,
)
from ..settings import settings


def discover_infrastructure(db: Session, node: Node) -> dict:
    from .common import _ansible_base_command

    command = f"{_ansible_base_command(node, 'service_infra_discovery_playbook.yml')}"
    job = create_job(db, action="discover-infra", command=command, node_id=node.id)

    if settings.local_mode:
        # Simulate discovering a PostgreSQL container and adopting it
        simulated_containers = [
            {
                "id": "pg-1001",
                "names": "platformops-postgres",
                "image": "postgres:15-alpine",
                "ports": "5432/tcp",
                "status": "Up 2 hours",
            }
        ]

        # Adopt running services matching catalog
        adopted_instances = []
        for container in simulated_containers:
            # Check similarity with database services
            existing = db.scalar(
                select(ServiceInstance).where(
                    ServiceInstance.node_id == node.id, ServiceInstance.container_name == container["names"]
                )
            )
            if not existing:
                service_key = "postgres-core"  # Default matched infrastructure key
                svc = ServiceInstance(
                    node_id=node.id,
                    service_key=service_key,
                    name="Adopted Postgres Database",
                    kind="infrastructure",
                    container_name=container["names"],
                    image=container["image"],
                    status="running",
                    config_json=json.dumps({"port": 5432, "adopted": True}),
                )
                db.add(svc)
                db.commit()
                db.refresh(svc)
                adopted_instances.append(svc)

        finish_job(db, job, ok=True, output=json.dumps(simulated_containers))
        return {
            "status": "success",
            "containers_scanned": len(simulated_containers),
            "adopted_count": len(adopted_instances),
            "adopted_services": [s.name for s in adopted_instances],
        }

    # Run discovery job asynchronously (not fully wired here, but structured for production)
    return {"status": "running", "message": "Infrastructure auto-discovery initiated."}
