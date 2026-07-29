# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.3",
#   "duckdb>=1.5.5",
#   "jsonschema>=4.26.0",
#   "pyarrow>=25",
#   "geoparquet-io @ git+https://github.com/yharby/geoparquet-io.git@f27e53108910f19bd74a9ff4be5c7d97b104753c",
#   "rasterio>=1.5",
#   "numpy",
#   "Pillow>=11",
#   "rio-cogeo>=5.3",
# ]
# ///
"""Offline checks for the raster-mosaic generator path."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import mosaic  # noqa: E402

FAILURES: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  ok   {name}")
    except AssertionError as exc:
        FAILURES.append(f"{name}: {exc}")
        print(f"  FAIL {name}: {exc}")


def _search_response(features: list[dict], next_link: bool = False) -> dict:
    links = [{"rel": "self", "href": "https://example.invalid/search"}]
    if next_link:
        links.append({"rel": "next", "href": "https://example.invalid/search?page=2"})
    return {"type": "FeatureCollection", "features": features, "links": links}


def _item(iid: str) -> dict:
    return {
        "type": "Feature", "id": iid, "collection": "naip",
        "bbox": [-105.0, 39.0, -104.9, 39.1],
        "geometry": {"type": "Polygon", "coordinates": [[
            [-105.0, 39.0], [-104.9, 39.0], [-104.9, 39.1], [-105.0, 39.1], [-105.0, 39.0]]]},
        "properties": {"datetime": "2023-10-20T16:00:00Z", "gsd": 0.3, "proj:epsg": 26913},
        "assets": {"image": {"href": f"https://example.invalid/{iid}.tif"}},
    }


def check_fetch_returns_features() -> None:
    with tempfile.TemporaryDirectory() as td:
        cache = Path(td) / "cache"
        cache.mkdir()
        payload = Path(td) / "resp.json"
        payload.write_text(json.dumps(_search_response([_item("a"), _item("b")])))
        got = mosaic.fetch_stac_items(payload.as_uri(), cache, stable=True)
        assert len(got) == 2, f"expected 2 items, got {len(got)}"
        assert got[0]["id"] == "a", got[0]["id"]


def check_fetch_rejects_unconsumed_page() -> None:
    with tempfile.TemporaryDirectory() as td:
        cache = Path(td) / "cache"
        cache.mkdir()
        payload = Path(td) / "resp.json"
        payload.write_text(json.dumps(_search_response([_item("a")], next_link=True)))
        try:
            mosaic.fetch_stac_items(payload.as_uri(), cache, stable=True)
        except SystemExit as exc:
            assert "next" in str(exc).lower(), str(exc)
            return
        raise AssertionError("a paged response must fail loudly")


import http.server  # noqa: E402
import threading  # noqa: E402

import stacio  # noqa: E402


class _SizedHandler(http.server.BaseHTTPRequestHandler):
    BODY = b"x" * 4242

    def do_HEAD(self) -> None:  # noqa: N802
        self.send_response(200)
        self.send_header("Content-Length", str(len(self.BODY)))
        self.end_headers()

    def log_message(self, *args) -> None:
        pass


class _NotFoundHandler(http.server.BaseHTTPRequestHandler):
    def do_HEAD(self) -> None:  # noqa: N802
        self.send_response(404)
        self.end_headers()

    def log_message(self, *args) -> None:
        pass


def check_remote_size() -> None:
    server = http.server.HTTPServer(("127.0.0.1", 0), _SizedHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/tile.tif"
        size = mosaic.remote_size(url)
        assert size == 4242, size
    finally:
        server.shutdown()
        server.server_close()


def check_remote_size_handles_404() -> None:
    server = http.server.HTTPServer(("127.0.0.1", 0), _NotFoundHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/missing.tif"
        try:
            mosaic.remote_size(url)
        except SystemExit as exc:
            assert url in str(exc), f"error message must name the href: {exc}"
            return
        raise AssertionError("remote_size must raise SystemExit on 404")
    finally:
        server.shutdown()
        server.server_close()


def check_remote_asset_has_size_and_no_checksum() -> None:
    a = stacio.remote_asset("https://example.invalid/t.tif", "image/tiff",
                            ["data"], "Tile", 4242, {"proj:code": "EPSG:26913"})
    assert a["file:size"] == 4242, a
    assert "file:checksum" not in a, "a checksum must never be invented"
    assert a["href"].startswith("https://"), a["href"]
    assert a["roles"] == ["data"], a
    assert a["proj:code"] == "EPSG:26913", a


if __name__ == "__main__":
    print("check_mosaic.py")
    check("fetch returns features", check_fetch_returns_features)
    check("fetch rejects an unconsumed next page", check_fetch_rejects_unconsumed_page)
    check("remote size comes from HEAD", check_remote_size)
    check("remote size handles 404", check_remote_size_handles_404)
    check("remote asset carries size and no checksum",
          check_remote_asset_has_size_and_no_checksum)
    if FAILURES:
        raise SystemExit(f"{len(FAILURES)} failure(s)")
    print("all ok")
