from fastapi import APIRouter

from .apis import docs_router, router

apis_router = APIRouter()
apis_router.include_router(router, tags=["API模块"])
api_docs_router = APIRouter()
api_docs_router.include_router(docs_router, tags=["API文档"])

__all__ = ["apis_router", "api_docs_router"]
