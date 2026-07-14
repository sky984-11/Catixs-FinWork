from fastapi import APIRouter

from .finance_quotes import router

finance_quotes_router = APIRouter()
finance_quotes_router.include_router(router, tags=["报价系统"])

__all__ = ["finance_quotes_router"]
