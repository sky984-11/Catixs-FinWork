from __future__ import annotations

import re
from urllib.parse import urljoin

import httpx
from fastapi import APIRouter, Query, Request, Response

from app.core.dependency import AuthControl
from app.settings.config import settings

router = APIRouter()

AKVORADO_REGIONS = {
    "SZ": "http://10.0.10.99:8081",
    "TW": "http://10.9.10.99:8081",
    "LA3": "http://10.3.10.90:8081",
    "DE": "http://10.7.10.89:8081",
    "HK": "http://10.4.10.39:8081",
    "SG": "http://10.6.10.53:8081",
    "LON": "http://10.1.10.208:8081",
    "JP": "http://10.5.10.17:8081",
}

HOP_BY_HOP_HEADERS = {
    "connection",
    "content-encoding",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "transfer-encoding",
    "upgrade",
}


def akvorado_proxy_prefix(region: str) -> str:
    return f"/api/v1/akvorado/proxy/{region}"


def rewrite_text_content(content: bytes, content_type: str, region: str) -> bytes:
    if not any(kind in content_type for kind in ("text/html", "text/css", "javascript", "application/json")):
        return content

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return content

    base = akvorado_proxy_prefix(region)
    base_slash = f"{base}/"
    upstream_base = AKVORADO_REGIONS[region].rstrip("/")

    text = text.replace(upstream_base, base)
    text = re.sub(r'((?:href|src|action)=["\'])/(?!/)', rf"\1{base_slash}", text)
    text = re.sub(r'(url\(["\']?)/(?!/)', rf"\1{base_slash}", text)
    text = re.sub(r'(["\'])/api/', rf"\1{base_slash}api/", text)
    text = re.sub(r'(["\'])/static/', rf"\1{base_slash}static/", text)
    if "text/html" in content_type and "<head" in text and "<base " not in text:
        text = re.sub(r"(<head[^>]*>)", rf'\1<base href="{base_slash}">', text, count=1, flags=re.I)
    return text.encode("utf-8")


@router.api_route(
    "/proxy/{region}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    summary="Proxy Akvorado region UI",
)
async def akvorado_proxy(region: str, path: str, request: Request, token: str = Query("")):
    region = region.upper()
    upstream_base = AKVORADO_REGIONS.get(region)
    if not upstream_base:
        return Response("Unknown Akvorado region", status_code=404, media_type="text/plain; charset=utf-8")

    auth_token = token or request.cookies.get("akvorado_proxy_token", "")
    try:
        await AuthControl.is_authed(token=auth_token)
    except Exception:
        return Response("Unauthorized", status_code=401, media_type="text/plain; charset=utf-8")

    target_url = urljoin(f"{upstream_base.rstrip('/')}/", path.lstrip("/"))
    upstream_params = [(key, value) for key, value in request.query_params.multi_items() if key != "token"]
    headers = {
        "Accept": request.headers.get("accept", "*/*"),
        "User-Agent": request.headers.get("user-agent", "Catixs-FinWork"),
    }
    for header_name in ("content-type", "accept-language", "cookie", "referer"):
        value = request.headers.get(header_name)
        if value:
            headers[header_name] = value

    body = await request.body()
    try:
        async with httpx.AsyncClient(
            timeout=settings.PDM_TIMEOUT,
            verify=False,
            trust_env=False,
            follow_redirects=False,
        ) as client:
            upstream = await client.request(
                request.method,
                target_url,
                params=upstream_params,
                content=body,
                headers=headers,
            )
    except httpx.RequestError as exc:
        return Response(
            f"Akvorado upstream request failed: {type(exc).__name__}: {exc}",
            status_code=502,
            media_type="text/plain; charset=utf-8",
        )

    proxy_prefix = akvorado_proxy_prefix(region)
    response_headers = {}
    for key, value in upstream.headers.items():
        lower = key.lower()
        if lower in HOP_BY_HOP_HEADERS:
            continue
        if lower == "location":
            if value.startswith(upstream_base):
                value = value.replace(upstream_base, proxy_prefix, 1)
            elif value.startswith("/"):
                value = f"{proxy_prefix}{value}"
        elif lower == "set-cookie":
            value = re.sub(r";\s*domain=[^;]+", "", value, flags=re.I)
            value = re.sub(r";\s*path=[^;]+", f"; Path={proxy_prefix}", value, flags=re.I)
        response_headers[key] = value

    content_type = upstream.headers.get("content-type", "")
    content = rewrite_text_content(upstream.content, content_type, region)
    response_headers["content-length"] = str(len(content))
    response = Response(content=content, status_code=upstream.status_code, headers=response_headers)
    if token:
        response.set_cookie(
            "akvorado_proxy_token",
            token,
            max_age=60 * 60,
            httponly=True,
            samesite="lax",
        )
    return response
