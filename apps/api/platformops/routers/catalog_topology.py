from __future__ import annotations

from fastapi import APIRouter

from . import ops_common as _ops_common
# Star-import does not pull private helpers; bind entire ops_common namespace.
globals().update({k: getattr(_ops_common, k) for k in dir(_ops_common) if not k.startswith("__")})

router = APIRouter(tags=["catalog_topology"])

@router.get("/api/catalog/services")
def list_catalog() -> list[dict]:
    return catalog_cards()


@router.get("/api/catalog/services/{service_key}/install-schema", response_model=ServiceInstallSchemaOut)
def get_service_install_schema(
    service_key: str,
    node_id: int,
    service_id: int | None = None,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    node = _get_node(db, node_id)
    service = _get_service(db, service_id) if service_id is not None else None
    return service_install_schema(db, service_key=service_key, node=node, service=service)


@router.get("/api/topology", response_model=TopologyOut)
def get_topology(db: Session = Depends(get_db)) -> dict:
    return topology(db)


@router.get("/api/events", response_model=list[OperationalEventOut])
def get_events(
    limit: int = 100,
    category: str | None = None,
    level: str | None = None,
    node_id: int | None = None,
    service_id: int | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
) -> list[OperationalEvent]:
    return list_events(
        db,
        limit=limit,
        category=category,
        level=level,
        node_id=node_id,
        service_id=service_id,
        search=search,
    )


@router.get("/api/capabilities/coverage", response_model=CapabilityCoverageOut)
def capabilities_coverage(db: Session = Depends(get_db)) -> dict:
    return capability_coverage_report(db)


@router.get("/api/dtrain/overview", response_model=DTrainOverview)
def get_dtrain_overview_endpoint(db: Session = Depends(get_db)) -> dict:
    return get_dtrain_overview(db)


