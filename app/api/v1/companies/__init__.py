from fastapi import APIRouter

from .companies import router

companies_router = APIRouter()
companies_router.include_router(router, tags=["公司模块"])

__all__ = ["companies_router"]