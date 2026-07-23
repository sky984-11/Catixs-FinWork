from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from tortoise.expressions import Q

from app.controllers.api import api_controller
from app.models.admin import Api
from app.models.enums import MethodType
from app.schemas import Success, SuccessExtra
from app.schemas.apis import *

router = APIRouter()
docs_router = APIRouter()

DOCS_PATH = "/api/v1/api/docs"
OPENAPI_DOCS_PATH = "/api/v1/api/docs/openapi"
SUPPORTED_API_METHODS = {item.value for item in MethodType}


def _normalize_methods(methods: dict, method: str | None):
    if not method:
        return methods.items()
    method_key = method.lower()
    if method_key not in methods:
        return []
    return [(method_key, methods[method_key])]


async def _build_api_docs(
    path: str | None = None,
    method: str | None = None,
    tags: str | None = None,
    include_public: bool = True,
):
    from app import app

    openapi_schema = app.openapi()
    items = []
    for route_path, methods in openapi_schema.get("paths", {}).items():
        if route_path in {DOCS_PATH, OPENAPI_DOCS_PATH}:
            continue
        if path and path not in route_path:
            continue

        for method_key, operation in _normalize_methods(methods, method):
            method_upper = method_key.upper()
            if method_upper not in SUPPORTED_API_METHODS:
                continue
            operation_tags = operation.get("tags") or []
            if tags and tags not in operation_tags:
                continue

            api_obj = await Api.filter(method=method_upper, path=route_path).first()
            if not include_public and not api_obj:
                continue

            items.append(
                {
                    "path": route_path,
                    "method": method_upper,
                    "summary": operation.get("summary", ""),
                    "description": operation.get("description", ""),
                    "tags": operation_tags,
                    "operation_id": operation.get("operationId", ""),
                    "parameters": operation.get("parameters", []),
                    "request_body": operation.get("requestBody"),
                    "responses": operation.get("responses", {}),
                    "deprecated": operation.get("deprecated", False),
                    "auth_required": bool(api_obj),
                }
            )

    items.sort(key=lambda item: (",".join(item["tags"]), item["path"], item["method"]))
    return {
        "title": openapi_schema.get("info", {}).get("title", ""),
        "version": openapi_schema.get("info", {}).get("version", ""),
        "docs_url": DOCS_PATH,
        "openapi_url": OPENAPI_DOCS_PATH,
        "total": len(items),
        "items": items,
    }


@docs_router.get("/docs", summary="公开API文档")
async def get_api_docs(
    path: str = Query(None, description="API路径"),
    method: str = Query(None, description="请求方式"),
    tags: str = Query(None, description="API模块"),
    include_public: bool = Query(True, description="是否包含无需权限的公开接口"),
):
    data = await _build_api_docs(
        path=path,
        method=method,
        tags=tags,
        include_public=include_public,
    )
    return Success(data=data)


@docs_router.get("/docs/openapi", summary="公开OpenAPI文档", include_in_schema=False)
async def get_openapi_docs():
    from app import app

    return JSONResponse(app.openapi())


@router.get("/list", summary="查看API列表")
async def list_api(
    page: int = Query(1, description="页码"),
    page_size: int = Query(10, description="每页数量"),
    path: str = Query(None, description="API路径"),
    summary: str = Query(None, description="API简介"),
    tags: str = Query(None, description="API模块"),
):
    q = Q()
    if path:
        q &= Q(path__contains=path)
    if summary:
        q &= Q(summary__contains=summary)
    if tags:
        q &= Q(tags__contains=tags)
    total, api_objs = await api_controller.list(page=page, page_size=page_size, search=q, order=["tags", "id"])
    data = [await obj.to_dict() for obj in api_objs]
    return SuccessExtra(data=data, total=total, page=page, page_size=page_size)


@router.get("/get", summary="查看Api")
async def get_api(
    id: int = Query(..., description="Api"),
):
    api_obj = await api_controller.get(id=id)
    data = await api_obj.to_dict()
    return Success(data=data)


@router.post("/create", summary="创建Api")
async def create_api(
    api_in: ApiCreate,
):
    await api_controller.create(obj_in=api_in)
    return Success(msg="Created Successfully")


@router.post("/update", summary="更新Api")
async def update_api(
    api_in: ApiUpdate,
):
    await api_controller.update(id=api_in.id, obj_in=api_in)
    return Success(msg="Update Successfully")


@router.delete("/delete", summary="删除Api")
async def delete_api(
    api_id: int = Query(..., description="ApiID"),
):
    await api_controller.remove(id=api_id)
    return Success(msg="Deleted Success")


@router.post("/refresh", summary="刷新API列表")
async def refresh_api():
    await api_controller.refresh_api()
    return Success(msg="OK")
