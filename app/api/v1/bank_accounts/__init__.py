from fastapi import APIRouter

from .bank_accounts import router

bank_accounts_router = APIRouter()
bank_accounts_router.include_router(router, tags=["银行账户模块"])

__all__ = ["bank_accounts_router"]

