from fastapi import APIRouter

from .vendors import router

vendors_router = APIRouter()
vendors_router.include_router(router, tags=["供应商模块"])

__all__ = ["vendors_router"]
