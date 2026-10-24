"""Minimal stateless MCP Streamable HTTP transport with JSON responses."""

import json
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response

from app.core.dependency import DependAuth
from app.models import User
from app.services.fw_database_mcp import PROTOCOL_VERSION, dispatch, rpc_error
from app.settings import settings

router = APIRouter()


def validate_origin(request: Request):
    origin = request.headers.get("origin")
    if origin is None:
        return
    # Do not use CORS '*' as an MCP origin allowlist.
    configured = [settings.WEB_BASE_URL, settings.WEB_DEV_BASE_URL, f"https://{settings.WEB_DOMAIN}"]
    configured += [value for value in settings.CORS_ORIGINS if value != "*"]
    allowed = set()
    for value in configured:
        parsed = urlsplit(str(value))
        if parsed.scheme in {"http", "https"} and parsed.netloc:
            allowed.add(f"{parsed.scheme}://{parsed.netloc}")
    if origin not in allowed:
        raise HTTPException(status_code=403, detail="MCP Origin is not allowed")


@router.get("/mcp", summary="MCP SSE stream is not supported")
async def mcp_get(request: Request, current_user: User = DependAuth):
    validate_origin(request)
    return Response(status_code=405, headers={"Allow": "POST", "Cache-Control": "no-store"})


@router.post(
    "/mcp",
    summary="FinWork read-only database MCP",
    description="MCP 2025-06-18 JSON-RPC endpoint. Requires FinWork authentication; see docs/rest-api.md.",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "required": ["jsonrpc", "method"],
                        "properties": {
                            "jsonrpc": {"type": "string", "enum": ["2.0"]},
                            "id": {"anyOf": [{"type": "integer"}, {"type": "string"}]},
                            "method": {"type": "string"},
                            "params": {"type": "object"},
                        },
                    }
                }
            },
        },
    },
)
async def mcp_post(request: Request, current_user: User = DependAuth):
    validate_origin(request)
    headers = {"Cache-Control": "no-store"}
    if request.headers.get("content-type", "").split(";", 1)[0].strip() != "application/json":
        raise HTTPException(status_code=415, detail="MCP requires application/json")
    accept = request.headers.get("accept", "")
    if "application/json" not in accept or "text/event-stream" not in accept:
        raise HTTPException(status_code=406, detail="Accept must include application/json and text/event-stream")
    if request.headers.get("mcp-protocol-version", PROTOCOL_VERSION) != PROTOCOL_VERSION:
        raise HTTPException(status_code=400, detail="Unsupported MCP protocol version")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > 65536:
            raise HTTPException(status_code=413, detail="MCP request exceeds 64 KiB")
    try:
        message = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return JSONResponse(rpc_error(None, -32700, "Parse error"), status_code=400, headers=headers)
    result = await dispatch(message, current_user)
    if result is None:
        return Response(status_code=202, headers=headers)
    return JSONResponse(result, headers=headers)
