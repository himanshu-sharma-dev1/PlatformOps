from __future__ import annotations

from fastapi import APIRouter

from . import services, nodes, sre, glitchtip, clusters, catalog_topology, observability, monitoring, diagnostics, misc

router = APIRouter()
router.include_router(services.router)
router.include_router(nodes.router)
router.include_router(sre.router)
router.include_router(glitchtip.router)
router.include_router(clusters.router)
router.include_router(catalog_topology.router)
router.include_router(observability.router)
router.include_router(monitoring.router)
router.include_router(diagnostics.router)
router.include_router(misc.router)
