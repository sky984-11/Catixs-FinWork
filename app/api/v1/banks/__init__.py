from fastapi import APIRouter

from .banks import router

banks_router = APIRouter()
banks_router.include_router(router, tags=["银行模块"])

__all__ = ["banks_router"]

