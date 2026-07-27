# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Standalone check for fetch.fetch's caching rule.

core.md requires an asset's file:size and file:checksum to be regenerated at
publish time so they match the bytes actually published. A source the manifest
marks `stable: false` is a live endpoint whose bytes drift, so serving it from a
cache written by an earlier build would describe bytes the endpoint no longer
returns. This asserts a stable source is cached and an unstable one is refetched,
against a local HTTP server whose body changes between requests.

Run: uv run examples/tools/tests/check_fetch.py
"""
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fetch import fetch  # noqa: E402


class _Drifting(BaseHTTPRequestHandler):
    """Serves a different body on every request, standing in for a live endpoint."""

    served = 0

    def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler's interface
        type(self).served += 1
        body = f"revision {type(self).served}".encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def main() -> int:
    server = HTTPServer(("127.0.0.1", 0), _Drifting)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/source.geojson"

    try:
        with tempfile.TemporaryDirectory() as d:
            cache = Path(d) / ".cache"

            first = fetch(url, cache, stable=True)
            assert first.read_bytes() == b"revision 1", first.read_bytes()

            # A stable source is fetched once and reused.
            again = fetch(url, cache, stable=True)
            assert again == first, (again, first)
            assert again.read_bytes() == b"revision 1", again.read_bytes()
            assert _Drifting.served == 1, f"stable source was fetched {_Drifting.served} times"

            # An unstable source refetches, so the bytes on disk are the bytes
            # this build's checksum and size will be derived from.
            live = fetch(url, cache, stable=False)
            assert live.read_bytes() == b"revision 2", live.read_bytes()
            assert _Drifting.served == 2, f"unstable source was fetched {_Drifting.served} times"

            live = fetch(url, cache, stable=False)
            assert live.read_bytes() == b"revision 3", live.read_bytes()
            assert _Drifting.served == 3, f"unstable source was fetched {_Drifting.served} times"
    finally:
        server.shutdown()

    print("OK, stable sources cache and unstable sources refetch")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
