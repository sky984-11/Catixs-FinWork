from urllib.parse import urlsplit

from starlette.requests import Request


_last_frontend_origin = ""


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


def remember_frontend_origin(request: Request) -> str:
    global _last_frontend_origin
    origin = get_frontend_origin_from_request(request)
    if origin:
        _last_frontend_origin = origin
    return origin


def get_last_frontend_origin() -> str:
    return _last_frontend_origin
