from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class NodeEnvironment(str, Enum):
    local = "local"
    aws = "aws"


class ServiceKind(str, Enum):
    app = "app"
    infrastructure = "infrastructure"
    helper = "helper"


class JobStatus(str, Enum):
    queued = "queued"
    running = "running"
    success = "success"
    failed = "failed"
    cancelled = "cancelled"


class Cluster(Base):
    __tablename__ = "clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    region: Mapped[str] = mapped_column(String(120), default="local")
    environment: Mapped[str] = mapped_column(String(80), default="development")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    nodes: Mapped[List["Node"]] = relationship(back_populates="cluster", cascade="all, delete-orphan")


class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    cluster_id: Mapped[int] = mapped_column(ForeignKey("clusters.id"))
    name: Mapped[str] = mapped_column(String(120))
    host: Mapped[str] = mapped_column(String(255))
    ssh_user: Mapped[str] = mapped_column(String(120), default="ubuntu")
    ssh_key_path: Mapped[str] = mapped_column(String(512), default="")
    environment: Mapped[str] = mapped_column(String(40), default=NodeEnvironment.local.value)
    volume_root: Mapped[str] = mapped_column(String(512), default="/tmp/platformops")
    docker_network: Mapped[str] = mapped_column(String(120), default="platformops_prod_network")
    status: Mapped[str] = mapped_column(String(40), default="unknown")
    facts_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    cluster: Mapped[Cluster] = relationship(back_populates="nodes")
    services: Mapped[List["ServiceInstance"]] = relationship(back_populates="node", cascade="all, delete-orphan")


class ServiceInstance(Base):
    __tablename__ = "service_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"))
    service_key: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(160))
    kind: Mapped[str] = mapped_column(String(40), default=ServiceKind.app.value)
    container_name: Mapped[str] = mapped_column(String(180))
    image: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(40), default="created")
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    node: Mapped[Node] = relationship(back_populates="services")
    jobs: Mapped[List["DeploymentJob"]] = relationship(back_populates="service", cascade="all, delete-orphan")
    snapshots: Mapped[List["ConfigSnapshot"]] = relationship(back_populates="service", cascade="all, delete-orphan")


class DeploymentJob(Base):
    __tablename__ = "deployment_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_instances.id"), nullable=True)
    node_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nodes.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(40), default=JobStatus.queued.value)
    command: Mapped[str] = mapped_column(Text, default="")
    output: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    service: Mapped[Optional[ServiceInstance]] = relationship(back_populates="jobs")


class ConfigSnapshot(Base):
    __tablename__ = "config_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service_instances.id"))
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(160))
    content: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(80), default="manual")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    service: Mapped[ServiceInstance] = relationship(back_populates="snapshots")


class OperationalEvent(Base):
    __tablename__ = "operational_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_instances.id"), nullable=True)
    node_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nodes.id"), nullable=True)
    category: Mapped[str] = mapped_column(String(80))
    level: Mapped[str] = mapped_column(String(40), default="info")
    message: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BackupRun(Base):
    __tablename__ = "backup_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service_instances.id"))
    status: Mapped[str] = mapped_column(String(40), default=JobStatus.queued.value)
    strategy: Mapped[str] = mapped_column(String(80), default="volume-archive")
    artifact_path: Mapped[str] = mapped_column(String(512), default="")
    output: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class MonitoringCheck(Base):
    __tablename__ = "monitoring_checks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_instances.id"), nullable=True)
    node_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nodes.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default="unknown")
    value: Mapped[str] = mapped_column(String(255), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class DeploymentPlanRecord(Base):
    __tablename__ = "deployment_plan_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"))
    service_key: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default="planned")
    plan_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class LogArchive(Base):
    __tablename__ = "log_archives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service_instances.id"))
    path: Mapped[str] = mapped_column(String(512))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    line_count: Mapped[int] = mapped_column(Integer, default=0)
    readable: Mapped[str] = mapped_column(String(20), default="unknown")
    reason: Mapped[str] = mapped_column(Text, default="")
    discovered_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ReleaseRecord(Base):
    __tablename__ = "release_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service_instances.id"))
    version: Mapped[str] = mapped_column(String(80))
    image: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(40), default="planned")
    strategy: Mapped[str] = mapped_column(String(80), default="rolling")
    notes: Mapped[str] = mapped_column(Text, default="")
    previous_image: Mapped[str] = mapped_column(String(255), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class DriftReport(Base):
    __tablename__ = "drift_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service_instances.id"))
    status: Mapped[str] = mapped_column(String(40), default="unknown")
    baseline_snapshot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("config_snapshots.id"), nullable=True)
    differences_json: Mapped[str] = mapped_column(Text, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class PolicyFinding(Base):
    __tablename__ = "policy_findings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_instances.id"), nullable=True)
    node_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nodes.id"), nullable=True)
    rule_id: Mapped[str] = mapped_column(String(120))
    severity: Mapped[str] = mapped_column(String(40), default="info")
    status: Mapped[str] = mapped_column(String(40), default="open")
    message: Mapped[str] = mapped_column(Text)
    remediation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class IncidentRecord(Base):
    __tablename__ = "incident_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_instances.id"), nullable=True)
    node_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nodes.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(180))
    severity: Mapped[str] = mapped_column(String(40), default="sev3")
    status: Mapped[str] = mapped_column(String(40), default="open")
    summary: Mapped[str] = mapped_column(Text, default="")
    remediation: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class RunbookExecution(Base):
    __tablename__ = "runbook_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    incident_id: Mapped[Optional[int]] = mapped_column(ForeignKey("incident_records.id"), nullable=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_instances.id"), nullable=True)
    node_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nodes.id"), nullable=True)
    runbook_key: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(40), default=JobStatus.queued.value)
    steps_json: Mapped[str] = mapped_column(Text, default="[]")
    output: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class SloReport(Base):
    __tablename__ = "slo_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_instances.id"), nullable=True)
    node_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nodes.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(120))
    target: Mapped[str] = mapped_column(String(80), default="99.9")
    observed: Mapped[str] = mapped_column(String(80), default="0")
    status: Mapped[str] = mapped_column(String(40), default="unknown")
    detail: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CapacityReport(Base):
    __tablename__ = "capacity_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    node_id: Mapped[int] = mapped_column(ForeignKey("nodes.id"))
    status: Mapped[str] = mapped_column(String(40), default="unknown")
    cpu_reserved: Mapped[str] = mapped_column(String(80), default="0")
    memory_reserved_mb: Mapped[int] = mapped_column(Integer, default=0)
    storage_reserved_gb: Mapped[int] = mapped_column(Integer, default=0)
    detail_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class SecretRecord(Base):
    __tablename__ = "secret_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_instances.id"), nullable=True)
    node_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nodes.id"), nullable=True)
    key: Mapped[str] = mapped_column(String(160))
    masked_value: Mapped[str] = mapped_column(String(255), default="********")
    scope: Mapped[str] = mapped_column(String(80), default="service")
    status: Mapped[str] = mapped_column(String(40), default="active")
    rotation_interval_days: Mapped[int] = mapped_column(Integer, default=90)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    rotated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class MaintenanceWindow(Base):
    __tablename__ = "maintenance_windows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[Optional[int]] = mapped_column(ForeignKey("service_instances.id"), nullable=True)
    node_id: Mapped[Optional[int]] = mapped_column(ForeignKey("nodes.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(40), default="scheduled")
    starts_at: Mapped[str] = mapped_column(String(80))
    ends_at: Mapped[str] = mapped_column(String(80))
    impact: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditExport(Base):
    __tablename__ = "audit_exports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    export_type: Mapped[str] = mapped_column(String(80), default="summary")
    status: Mapped[str] = mapped_column(String(40), default="ready")
    artifact_path: Mapped[str] = mapped_column(String(512), default="")
    content_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class ForceDeleteApproval(Base):
    __tablename__ = "force_delete_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    target_type: Mapped[str] = mapped_column(String(40))
    target_id: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text, default="")
    requested_by: Mapped[str] = mapped_column(String(160), default="platform-operator")
    status: Mapped[str] = mapped_column(String(40), default="pending")
    approver: Mapped[str] = mapped_column(String(160), default="")
    decision_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class ReleaseApproval(Base):
    __tablename__ = "release_approvals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    service_id: Mapped[int] = mapped_column(ForeignKey("service_instances.id"))
    target_version: Mapped[str] = mapped_column(String(120), default="")
    target_image: Mapped[str] = mapped_column(String(255), default="")
    reason: Mapped[str] = mapped_column(Text, default="")
    requested_by: Mapped[str] = mapped_column(String(160), default="platform-operator")
    status: Mapped[str] = mapped_column(String(40), default="pending")
    approver: Mapped[str] = mapped_column(String(160), default="")
    decision_note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
