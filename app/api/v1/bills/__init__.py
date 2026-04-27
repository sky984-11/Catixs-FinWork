from fastapi import APIRouter

from .bills import router

bills_router = APIRouter()
bills_router.include_router(router, tags=["账单模块"])

__all__ = ["bills_router"]

