"""Minimal POC host page + guest token endpoint (stdlib only, local dev only).

GET /       -> index.html
GET /token  -> {"token": "<guest token>"} for the embedded dashboard
"""

import http.cookiejar
import json
import os
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

SUPERSET_URL = os.environ.get("SUPERSET_URL", "http://localhost:8088")
# Docker dev defaults; dummy POC data only.
SUPERSET_USER = os.environ.get("SUPERSET_USER", "admin")
SUPERSET_PASSWORD = os.environ.get("SUPERSET_PASSWORD", "admin")
EMBED_UUID = os.environ.get("EMBED_UUID", "972c2722-ae3a-4344-ae77-072a582825be")
HERE = os.path.dirname(os.path.abspath(__file__))


def _request(opener, path, data=None, headers=None):
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(
        SUPERSET_URL + path,
        data=body,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST" if body is not None else "GET",
    )
    with opener.open(req, timeout=15) as resp:
        return json.loads(resp.read())


def fetch_guest_token():
    # Cookie jar keeps the session cookie the CSRF token is bound to.
    opener = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )
    login = _request(
        opener,
        "/api/v1/security/login",
        {
            "username": SUPERSET_USER,
            "password": SUPERSET_PASSWORD,
            "provider": "db",
            "refresh": True,
        },
    )
    auth = {"Authorization": f"Bearer {login['access_token']}"}
    csrf = _request(opener, "/api/v1/security/csrf_token/", headers=auth)["result"]
    result = _request(
        opener,
        "/api/v1/security/guest_token/",
        {
            "user": {"username": "poc_guest", "first_name": "POC", "last_name": "Guest"},
            "resources": [{"type": "dashboard", "id": EMBED_UUID}],
            "rls": [],
        },
        headers={**auth, "X-CSRFToken": csrf, "Referer": SUPERSET_URL},
    )
    return result["token"]


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=HERE, **kwargs)

    def do_GET(self):
        if self.path.split("?")[0] == "/token":
            try:
                payload, status = {"token": fetch_guest_token()}, 200
            except Exception as ex:  # surface Superset errors to the caller
                detail = ex.read().decode() if hasattr(ex, "read") else str(ex)
                payload, status = {"error": detail}, 502
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.split("?")[0] not in ("/", "/index.html"):
            self.send_error(404)
            return
        self.path = "/index.html"
        super().do_GET()


if __name__ == "__main__":
    print("Serving on http://0.0.0.0:8000")
    ThreadingHTTPServer(("0.0.0.0", 8000), Handler).serve_forever()
