from http.client import HTTPConnection
from http.cookies import SimpleCookie

from django.conf import settings
from django.http import Http404, HttpResponse
from django.views.decorators.csrf import csrf_exempt


HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailers",
    "transfer-encoding",
    "upgrade",
}
ADMISSION_PREFIX = "/admission"
ADMISSION_UPSTREAM = ("127.0.0.1", 8001)


@csrf_exempt
def proxy_admission(request, path=""):
    if not settings.DEBUG:
        raise Http404

    upstream_path = f"/{path}"
    if request.META.get("QUERY_STRING"):
        upstream_path = f"{upstream_path}?{request.META['QUERY_STRING']}"

    headers = {
        "Host": request.get_host(),
        "X-Forwarded-For": request.META.get("REMOTE_ADDR", ""),
        "X-Forwarded-Proto": request.scheme,
        "X-Forwarded-Prefix": ADMISSION_PREFIX,
        "Accept-Encoding": "identity",
    }
    for meta_name, value in request.META.items():
        if not meta_name.startswith("HTTP_"):
            continue
        header_name = meta_name[5:].replace("_", "-").title()
        if header_name.lower() not in HOP_BY_HOP_HEADERS | {
            "host",
            "x-forwarded-for",
            "x-forwarded-proto",
            "x-forwarded-prefix",
        }:
            headers[header_name] = value
    if request.META.get("CONTENT_TYPE"):
        headers["Content-Type"] = request.META["CONTENT_TYPE"]

    try:
        upstream = HTTPConnection(*ADMISSION_UPSTREAM, timeout=10)
        upstream.request(
            request.method,
            upstream_path,
            body=request.body if request.method not in {"GET", "HEAD"} else None,
            headers=headers,
        )
        upstream_response = upstream.getresponse()
        content = upstream_response.read()
        response = HttpResponse(
            content,
            status=upstream_response.status,
            reason=upstream_response.reason,
        )
        for header_name, value in upstream_response.getheaders():
            if header_name.lower() == "set-cookie":
                cookies = SimpleCookie()
                cookies.load(value)
                response.cookies.update(cookies)
            elif header_name.lower() not in HOP_BY_HOP_HEADERS | {
                "content-length",
            }:
                response[header_name] = value
        return response
    except OSError:
        return HttpResponse(
            "Le portail d'admission n'est pas demarre. Lancez-le sur le port 8001.",
            status=502,
            content_type="text/plain; charset=utf-8",
        )
    finally:
        if "upstream" in locals():
            upstream.close()
