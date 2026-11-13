# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.3", "awscli==1.46.3"]
# ///
"""Standalone check that publish_catalogs.py syncs and tears down through the proxy.

The real target is Source Cooperative's data proxy, which routes S3 requests in
its own way. It maps a request to a product only when the path starts with
/<account>/<product>, or when an account-level LIST names the product in its
prefix. Its LIST answers with account-relative keys, `<product>/<rest>`, even
when the product is in the URL path. And it answers a batch delete under the
account alone, POST /<account>?delete, with NoSuchBucket.

s5cmd tripped over all three, and a string check of the URLs could not see it.
This runs the real sync and teardown, through the pinned AWS CLI, against a
local stand-in that routes the way the proxy does. The stand-in starts primed
with objects already on the remote, so the check proves that the sync removes
a stale file, that the teardown removes a whole preview, that neighbouring
prefixes survive both, and that a listing with keys outside the prefix fails
the teardown rather than passing it as empty.

Offline, no credentials. Run: uv run examples/tools/tests/check_publish_proxy.py
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import publish_catalogs as pc  # noqa: E402

ACCOUNT = pc.ACCOUNT
PRODUCT = pc.PRODUCT


class FakeProxy:
    """The routing of data.source.coop over an in-memory object store.

    Keys in `objects` are account-relative, `<product>/<rest>`, which is how
    the proxy reports them. `list_shape` switches the LIST answer to a broken
    one, product-relative keys, to prove the teardown refuses it.
    """

    def __init__(self, objects: dict[str, bytes]):
        self.objects = dict(objects)
        self.parts: dict[str, dict[int, bytes]] = {}
        self.requests: list[tuple[str, str, dict[str, str]]] = []
        self.list_shape = "account-relative"
        self.lock = threading.Lock()


def _list_xml(account: str, prefix: str, keys: list[str]) -> bytes:
    contents = "".join(
        f"<Contents><Key>{escape(key)}</Key>"
        "<LastModified>2026-01-01T00:00:00.000Z</LastModified>"
        f'<ETag>"e"</ETag><Size>1</Size><StorageClass>STANDARD</StorageClass>'
        "</Contents>"
        for key in keys
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<ListBucketResult xmlns="http://s3.amazonaws.com/doc/2006-03-01/">'
        f"<Name>{account}</Name><Prefix>{escape(prefix)}</Prefix>"
        f"<MaxKeys>1000</MaxKeys><IsTruncated>false</IsTruncated>"
        f"<KeyCount>{len(keys)}</KeyCount>{contents}</ListBucketResult>"
    ).encode()


def _error(code: str, message: str) -> bytes:
    return (
        f'<?xml version="1.0" encoding="UTF-8"?><Error><Code>{code}</Code>'
        f"<Message>{escape(message)}</Message></Error>"
    ).encode()


def make_handler(proxy: FakeProxy):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):
            pass

        def _body(self) -> bytes:
            if "chunked" in self.headers.get("Transfer-Encoding", ""):
                out = b""
                while True:
                    size = int(self.rfile.readline().split(b";")[0], 16)
                    if size == 0:
                        self.rfile.readline()
                        return out
                    out += self.rfile.read(size)
                    self.rfile.readline()
            length = int(self.headers.get("Content-Length") or 0)
            return self.rfile.read(length) if length else b""

        def _send(self, status: int, body: bytes = b"", extra=None):
            self.send_response(status)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("ETag", '"e"')
            for name, value in (extra or {}).items():
                self.send_header(name, value)
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _route(self):
            url = urllib.parse.urlsplit(self.path)
            query = urllib.parse.parse_qs(url.query, keep_blank_values=True)
            segments = urllib.parse.unquote(url.path).strip("/").split("/", 2)
            with proxy.lock:
                proxy.requests.append((self.command, self.path, dict(self.headers)))
            return query, segments

        def _keys_under(self, prefix: str) -> list[str]:
            with proxy.lock:
                keys = sorted(k for k in proxy.objects if k.startswith(prefix))
            if proxy.list_shape == "product-relative":
                keys = [k.split("/", 1)[1] for k in keys]
            return keys

        def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler's interface
            query, segments = self._route()
            if "list-type" in query:
                prefix = query.get("prefix", [""])[0]
                if len(segments) == 1 and segments[0] == ACCOUNT and "/" in prefix:
                    # /<account>?list-type=2&prefix=<product>/<rest>
                    return self._send(200, _list_xml(ACCOUNT, prefix, self._keys_under(prefix)))
                if len(segments) == 2 and segments[0] == ACCOUNT:
                    # /<account>/<product>?list-type=2, still account-relative
                    full = f"{segments[1]}/{prefix}"
                    return self._send(200, _list_xml(ACCOUNT, full, self._keys_under(full)))
                return self._send(400, _error("InvalidRequest", "unmapped list"))
            if len(segments) == 3:
                key = f"{segments[1]}/{segments[2]}"
                with proxy.lock:
                    body = proxy.objects.get(key)
                if body is not None:
                    return self._send(200, body)
            self._send(404, _error("NoSuchKey", "no such key"))

        def do_HEAD(self):  # noqa: N802
            self.do_GET()

        def do_PUT(self):  # noqa: N802
            query, segments = self._route()
            body = self._body()
            if len(segments) != 3 or segments[0] != ACCOUNT:
                return self._send(400, _error("InvalidRequest", "missing object key"))
            key = f"{segments[1]}/{segments[2]}"
            with proxy.lock:
                if "uploadId" in query:
                    part = int(query["partNumber"][0])
                    proxy.parts.setdefault(key, {})[part] = body
                else:
                    proxy.objects[key] = body
            self._send(200)

        def do_POST(self):  # noqa: N802
            query, segments = self._route()
            body = self._body()
            if "delete" in query:
                if len(segments) == 1:
                    # The proxy cannot map a batch delete under the account.
                    return self._send(404, _error("NoSuchBucket", f"bucket not found: {segments[0]}"))
                keys = [
                    f"{segments[1]}/{m.decode()}"
                    for m in re.findall(rb"<Key>(.*?)</Key>", body)
                ]
                with proxy.lock:
                    for key in keys:
                        proxy.objects.pop(key, None)
                deleted = "".join(f"<Deleted><Key>{escape(k)}</Key></Deleted>" for k in keys)
                return self._send(200, f"<DeleteResult>{deleted}</DeleteResult>".encode())
            if len(segments) != 3:
                return self._send(400, _error("InvalidRequest", "missing object key"))
            key = f"{segments[1]}/{segments[2]}"
            if "uploads" in query:
                return self._send(
                    200,
                    "<InitiateMultipartUploadResult>"
                    f"<Bucket>{ACCOUNT}</Bucket><Key>{escape(segments[1] + '/' + segments[2])}</Key>"
                    "<UploadId>u1</UploadId></InitiateMultipartUploadResult>".encode(),
                )
            with proxy.lock:
                parts = proxy.parts.pop(key, {})
                proxy.objects[key] = b"".join(parts[n] for n in sorted(parts))
            self._send(
                200,
                "<CompleteMultipartUploadResult>"
                f'<Key>{escape(key)}</Key><ETag>"e"</ETag>'
                "</CompleteMultipartUploadResult>".encode(),
            )

        def do_DELETE(self):  # noqa: N802
            query, segments = self._route()
            if len(segments) != 3:
                return self._send(400, _error("InvalidRequest", "missing object key"))
            if "uploadId" not in query:
                with proxy.lock:
                    proxy.objects.pop(f"{segments[1]}/{segments[2]}", None)
            self._send(204)

    return Handler


def start(proxy: FakeProxy) -> tuple[ThreadingHTTPServer, str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(proxy))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_address[1]}"


def isolate_cli_env() -> None:
    """Fake credentials and no user config, so nothing here can reach AWS."""
    os.environ.update(
        AWS_ACCESS_KEY_ID="AKIDEXAMPLE",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_SESSION_TOKEN="token",
        AWS_REGION="us-west-2",
        AWS_DEFAULT_REGION="us-west-2",
        AWS_CONFIG_FILE=os.devnull,
        AWS_SHARED_CREDENTIALS_FILE=os.devnull,
    )
    for name in ("AWS_PROFILE", "AWS_ENDPOINT_URL", "AWS_ENDPOINT_URL_S3"):
        os.environ.pop(name, None)


def main() -> int:
    failures: list[str] = []
    isolate_cli_env()

    preview = f"{PRODUCT}/cat/PRs/7/"
    neighbours = {
        f"{PRODUCT}/cat/main/catalog.json": b"main",
        f"{PRODUCT}/cat/PRs/70/catalog.json": b"pr 70",
        f"{PRODUCT}/other/PRs/7/catalog.json": b"other",
    }
    proxy = FakeProxy({f"{preview}stale.json": b"old", **neighbours})
    server, endpoint = start(proxy)
    pc.S3_ENDPOINT = endpoint

    def under(prefix: str) -> set[str]:
        return {k.removeprefix(prefix) for k in proxy.objects if k.startswith(prefix)}

    def expect_exit(label: str, call) -> None:
        try:
            call()
        except SystemExit as exc:
            print(f"refused as expected, {label}: {exc}")
            return
        failures.append(f"{label}: expected a failure, the call passed")

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tree = Path(tmp) / "cat"
            (tree / "sub").mkdir(parents=True)
            (tree / "catalog.json").write_text('{"id": "cat"}')
            (tree / "sub" / "item.json").write_text("{}")
            (tree / ".DS_Store").write_bytes(b"finder")
            # Over the CLI's 8 MiB threshold, so the multipart path runs too.
            (tree / "sub" / "big.bin").write_bytes(os.urandom(9 * 1024 * 1024))

            target, _ = pc.destination("cat", "PRs/7")
            pc.sync(tree, target, dry_run=False)
            want = {"catalog.json", "sub/item.json", "sub/big.bin"}
            if under(preview) != want:
                failures.append(f"after sync the preview holds {sorted(under(preview))}")
            if len(proxy.objects.get(f"{preview}sub/big.bin", b"")) != 9 * 1024 * 1024:
                failures.append("the multipart upload did not reassemble")

            # A dry run must leave every object where it is.
            pc.teardown(["cat"], "7", dry_run=True)
            if under(preview) != want:
                failures.append("a dry-run teardown deleted objects")

            pc.teardown(["cat"], "7", dry_run=False)
            if under(preview):
                failures.append(f"teardown left {sorted(under(preview))}")

            # Nothing under the prefix is the one listing that may pass empty.
            pc.teardown(["cat"], "7", dry_run=False)

            for key, body in neighbours.items():
                if proxy.objects.get(key) != body:
                    failures.append(f"a neighbouring object was touched, {key}")

            # Product-relative keys are the shape that made s5cmd see nothing.
            proxy.objects[f"{preview}catalog.json"] = b"{}"
            proxy.list_shape = "product-relative"
            expect_exit("teardown on a mismatched listing", lambda: pc.teardown(["cat"], "7", False))
            expect_exit("sync on a mismatched listing", lambda: pc.sync(tree, target, False))
            proxy.list_shape = "account-relative"
    finally:
        server.shutdown()

    batch = [path for method, path, _ in proxy.requests if method == "POST" and "delete" in path]
    if batch:
        failures.append(f"a batch delete was sent, which the proxy cannot map: {batch}")
    # Every request is either an account-level LIST naming the product in its
    # prefix, or an object request under /<account>/<product>/. Anything else
    # is a key this script misread, the way s5cmd misread the listing.
    outside = []
    for method, path, _ in proxy.requests:
        url = urllib.parse.urlsplit(path)
        query = urllib.parse.parse_qs(url.query)
        if url.path == f"/{ACCOUNT}" and "list-type" in query:
            if query.get("prefix", [""])[0].startswith(f"{PRODUCT}/"):
                continue
        elif urllib.parse.unquote(url.path).startswith(f"/{ACCOUNT}/{PRODUCT}/"):
            continue
        outside.append(f"{method} {path}")
    if outside:
        failures.append(f"requests outside the product: {outside[:3]}")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    if not failures:
        print(f"publish through the proxy ok, {len(proxy.requests)} requests")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
