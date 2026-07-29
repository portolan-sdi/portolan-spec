# /// script
# requires-python = ">=3.12"
# dependencies = ["rasterio>=1.5", "numpy", "Pillow>=11"]
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


if __name__ == "__main__":
    print("check_mosaic.py")
    check("fetch returns features", check_fetch_returns_features)
    check("fetch rejects an unconsumed next page", check_fetch_rejects_unconsumed_page)
    if FAILURES:
        raise SystemExit(f"{len(FAILURES)} failure(s)")
    print("all ok")
