"""cPlatform-compatible service external ID allocation (SERV####)."""

from __future__ import annotations

from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ServiceInstance

SERVICE_BASE_IDX = 1000


def allocate_service_external_id(
    db: Session,
    *,
    discovered_names: Iterable[str] | None = None,
    preferred_start: int | None = None,
) -> str:
    """
    Allocate next free SERV#### that is not already used as external_id
    and does not clash with reserved discovered container names.
    """
    existing_ids = {
        str(value).strip()
        for value in db.scalars(select(ServiceInstance.external_id)).all()
        if value and str(value).strip()
    }
    # Also treat bare container names that look like SERV#### as reserved
    existing_names = {
        str(value).strip()
        for value in db.scalars(select(ServiceInstance.container_name)).all()
        if value and str(value).strip()
    }
    reserved = set(existing_ids) | set(existing_names)
    if discovered_names:
        for name in discovered_names:
            token = str(name or "").strip().lstrip("/")
            if token:
                reserved.add(token)

    candidate_num = preferred_start if preferred_start is not None else SERVICE_BASE_IDX
    # Prefer growing past max existing SERV number when possible
    max_seen = SERVICE_BASE_IDX - 1
    for token in existing_ids:
        if token.upper().startswith("SERV"):
            try:
                max_seen = max(max_seen, int(token[4:]))
            except ValueError:
                continue
    if preferred_start is None:
        candidate_num = max(SERVICE_BASE_IDX, max_seen + 1)

    while True:
        candidate = f"SERV{candidate_num}"
        if candidate not in reserved:
            return candidate
        candidate_num += 1


def ensure_service_external_id(db: Session, service: ServiceInstance) -> str:
    """Assign external_id if missing; commit is caller's responsibility for batch."""
    if service.external_id and str(service.external_id).strip():
        return str(service.external_id)
    external = allocate_service_external_id(db, preferred_start=SERVICE_BASE_IDX + int(service.id or 0))
    # If preferred collides, allocate free
    service.external_id = external
    return external
