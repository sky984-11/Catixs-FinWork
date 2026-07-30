from fastapi import APIRouter

from .resources import router

resources_router = APIRouter()
resources_router.include_router(router, tags=["资源模块"])
