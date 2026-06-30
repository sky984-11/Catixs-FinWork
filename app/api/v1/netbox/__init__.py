from fastapi import APIRouter

from .ipam import router

netbox_router = APIRouter()
netbox_router.include_router(router, tags=["NetBox IPAM"])

__all__ = ["netbox_router"]
