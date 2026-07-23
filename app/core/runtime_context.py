from urllib.parse import urlsplit

from starlette.requests import Request


_last_frontend_origin = ""
_last_request_origin = ""


def is_local_origin(origin: str) -> bool:
    parts = urlsplit(str(origin or ""))
    host = (parts.hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}


def get_frontend_origin_from_request(request: Request) -> str:
    origin = request.headers.get("origin", "").rstrip("/")
    if origin:
        return origin

    referer = request.headers.get("referer", "")
    if referer:
        parts = urlsplit(referer)
        if parts.scheme and parts.netloc:
            return f"{parts.scheme}://{parts.netloc}".rstrip("/")

    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host") or request.headers.get("host")
    if forwarded_proto and forwarded_host:
        return f"{forwarded_proto}://{forwarded_host}".rstrip("/")

    return str(request.base_url).rstrip("/")


def get_request_origin_from_request(request: Request) -> str:
    forwarded_proto = request.headers.get("x-forwarded-proto")
    forwarded_host = request.headers.get("x-forwarded-host")
    if forwarded_host:
        proto = (forwarded_proto or request.url.scheme or "http").split(",", 1)[0].strip()
        host = forwarded_host.split(",", 1)[0].strip()
        return f"{proto}://{host}".rstrip("/")

    host = request.headers.get("host", "").strip()
    if host:
        return f"{request.url.scheme or 'http'}://{host}".rstrip("/")

    return str(request.base_url).rstrip("/")


def remember_frontend_origin(request: Request) -> str:
    global _last_frontend_origin, _last_request_origin
    origin = get_frontend_origin_from_request(request)
    request_origin = get_request_origin_from_request(request)
    if origin and not is_local_origin(origin):
        _last_frontend_origin = origin
    if request_origin and not is_local_origin(request_origin):
        _last_request_origin = request_origin
    return origin


def get_last_frontend_origin() -> str:
    return _last_frontend_origin


def get_last_request_origin() -> str:
    return _last_request_origin
