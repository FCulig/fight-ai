"""Local preview of the landing page (the `landing` entry in .claude/launch.json).

Serves landing/ like Caddy does in production, and like Caddy forwards
POST /api/auth/waitlist to the backend, so the waitlist form posts to its own
origin in dev as well. Start the backend (port 8000) to submit the form.

    python3 landing/dev_server.py [port]
"""
import sys
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BACKEND = "http://127.0.0.1:8000"
WAITLIST = "/api/auth/waitlist"


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != WAITLIST:
            self.send_error(404)
            return
        body = self.rfile.read(int(self.headers.get("Content-Length") or 0))
        req = urllib.request.Request(
            BACKEND + WAITLIST, data=body, method="POST",
            headers={"Content-Type": self.headers.get("Content-Type", "application/json")},
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                status, payload, ctype = resp.status, resp.read(), resp.headers.get("Content-Type")
        except urllib.error.HTTPError as e:
            status, payload, ctype = e.code, e.read(), e.headers.get("Content-Type")
        except urllib.error.URLError:
            self.send_error(502, "Backend not running on port 8000")
            return
        self.send_response(status)
        if ctype:
            self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4321
    handler = partial(Handler, directory=str(Path(__file__).parent))
    print(f"Landing on http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
