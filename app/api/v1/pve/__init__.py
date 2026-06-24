from fastapi import APIRouter

from .novnc import router as novnc_router
from .pve import grafana_router
from .pve import router as datacenter_router
from .vm_create import router as vm_create_router

pve_router = APIRouter()
pve_router.include_router(datacenter_router)
pve_router.include_router(vm_create_router)
pve_router.include_router(novnc_router)
