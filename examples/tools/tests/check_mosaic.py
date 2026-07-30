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

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import mosaic  # noqa: E402
import thumbnails  # noqa: E402

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

import numpy as np  # noqa: E402
import rasterio  # noqa: E402
from rasterio.transform import from_origin  # noqa: E402

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


def _write_cog(path: Path, overviews: bool = True) -> None:
    """A small 2-band GeoTIFF with optional overviews, enough to exercise the reader."""
    data = np.zeros((2, 1024, 1024), dtype="uint8")
    data[0, :512, :] = 10
    data[0, 512:, :] = 250
    data[1, :, :] = 100
    profile = {"driver": "GTiff", "height": 1024, "width": 1024, "count": 2,
               "dtype": "uint8", "crs": "EPSG:26913",
               "transform": from_origin(500000, 4400000, 0.3, 0.3),
               "tiled": True, "blockxsize": 512, "blockysize": 512}
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)
        if overviews:
            dst.build_overviews([2, 4])


def check_read_overview() -> None:
    with tempfile.TemporaryDirectory() as td:
        tif = Path(td) / "t.tif"
        _write_cog(tif)
        bands, arr = mosaic.read_overview(str(tif))
        assert len(bands) == 2, bands
        assert arr.shape[0] == 2, arr.shape
        assert arr.shape[1] < 1024, f"must read an overview, not full res, got {arr.shape}"
        stats = bands[0]["statistics"]
        for key in ("minimum", "maximum", "mean", "stddev"):
            assert key in stats, f"{key} missing from {stats}"
        assert stats["minimum"] == 10, stats
        assert stats["maximum"] == 250, stats
        assert bands[0]["data_type"] == "uint8", bands[0]
        assert bands[0]["statistics"]["approximate"] is True, \
            "overview-derived statistics must be flagged approximate"


def check_read_overview_rejects_no_overviews() -> None:
    with tempfile.TemporaryDirectory() as td:
        tif = Path(td) / "t.tif"
        _write_cog(tif, overviews=False)
        try:
            mosaic.read_overview(str(tif))
        except SystemExit as exc:
            assert str(tif) in str(exc), f"error message must name the path: {exc}"
            assert "overview" in str(exc).lower(), f"error must mention overviews: {exc}"
            return
        raise AssertionError("read_overview must raise SystemExit when no overviews are found")


def check_read_overview_rejects_unreadable() -> None:
    with tempfile.TemporaryDirectory() as td:
        txt = Path(td) / "t.txt"
        txt.write_text("not a raster")
        try:
            mosaic.read_overview(str(txt))
        except SystemExit as exc:
            assert str(txt) in str(exc), f"error message must name the path: {exc}"
            return
        raise AssertionError("read_overview must raise SystemExit for unreadable input")


def check_build_items() -> None:
    with tempfile.TemporaryDirectory() as td:
        coll = Path(td) / "colorado-2023"
        coll.mkdir(parents=True)
        feats = [_item("a"), _item("b")]

        def fake_probe(href: str):
            return 4242, [{"data_type": "uint8", "statistics": {
                "minimum": 1.0, "maximum": 2.0, "mean": 1.5,
                "stddev": 0.5, "approximate": True}}], np.zeros((1, 4, 4), "uint8")

        items, links, bbox, tiles = mosaic.build_items(
            feats, coll, "imagery/colorado-2023", "NAIP Colorado 2023", fake_probe)

        assert len(items) == 2 and len(links) == 2, (len(items), len(links))
        assert bbox == [-105.0, 39.0, -104.9, 39.1], bbox
        assert len(tiles) == 2, tiles
        assert tiles[0][0] == feats[0]["bbox"], tiles[0][0]
        assert tiles[0][1].shape == (1, 4, 4), tiles[0][1].shape

        written = json.loads((coll / "a" / "item.json").read_text())
        assert written["type"] == "Feature", written["type"]
        assert written["stac_version"] == "1.1.0", written["stac_version"]
        assert written["collection"] == "imagery/colorado-2023", written["collection"]
        assert written["properties"]["datetime"] == "2023-10-20T16:00:00Z", written["properties"]
        assert written["properties"]["proj:code"] == "EPSG:26913", written["properties"]

        img = written["assets"]["image"]
        assert img["href"] == "https://example.invalid/a.tif", img["href"]
        assert img["file:size"] == 4242, img
        assert "file:checksum" not in img, "no invented checksum on a remote asset"
        assert img["roles"] == ["data"], img
        assert img["bands"][0]["statistics"]["approximate"] is True, img["bands"]

        rels = {entry["rel"]: entry["href"] for entry in written["links"]}
        assert rels["root"] == "../../../catalog.json", rels
        assert rels["parent"] == "../collection.json", rels
        assert rels["collection"] == "../collection.json", rels
        assert "self" not in rels, "objects must not carry a self link"

        assert links[0]["rel"] == "item", links[0]
        assert links[0]["href"] == "./a/item.json", links[0]
        assert links[0]["type"] == "application/geo+json", links[0]
        assert links[0]["title"] == "a", links[0]


def check_build_items_rejects_missing_datetime() -> None:
    with tempfile.TemporaryDirectory() as td:
        coll = Path(td) / "colorado-2023"
        coll.mkdir(parents=True)
        feat = _item("zz-tile-0417")
        del feat["properties"]["datetime"]

        def fake_probe(href: str):
            return 4242, [], np.zeros((1, 4, 4), "uint8")

        try:
            mosaic.build_items([feat], coll, "imagery/colorado-2023", "NAIP", fake_probe)
        except SystemExit as exc:
            assert "zz-tile-0417" in str(exc), str(exc)
            assert "datetime" in str(exc).lower(), str(exc)
            return
        raise AssertionError("a feature with no datetime must fail loudly")


def check_build_items_rejects_missing_image_asset() -> None:
    with tempfile.TemporaryDirectory() as td:
        coll = Path(td) / "colorado-2023"
        coll.mkdir(parents=True)
        feat = _item("zz-tile-0417")
        del feat["assets"]["image"]

        def fake_probe(href: str):
            return 4242, [], np.zeros((1, 4, 4), "uint8")

        try:
            mosaic.build_items([feat], coll, "imagery/colorado-2023", "NAIP", fake_probe)
        except SystemExit as exc:
            assert "zz-tile-0417" in str(exc), str(exc)
            return
        raise AssertionError("a feature with no image asset must fail loudly")


def check_minimal_json() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "minimal.json"
        items = [
            {"bbox": [-105.0, 39.0, -104.9, 39.1],
             "assets": {"image": {"href": "https://example.invalid/a.tif",
                                  "type": "image/tiff", "file:size": 1}}},
        ]
        n = mosaic.write_minimal_json(items, out)
        doc = json.loads(out.read_text())
        assert n == 1, n
        assert doc["type"] == "FeatureCollection", doc["type"]
        feat = doc["features"][0]
        assert set(feat) == {"bbox", "assets"}, f"minimal shape only, got {set(feat)}"
        assert feat["bbox"] == items[0]["bbox"], feat["bbox"]
        assert set(feat["assets"]["image"]) == {"href"}, feat["assets"]["image"]
        assert feat["assets"]["image"]["href"] == "https://example.invalid/a.tif"


def check_thumbnail_mosaic() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "thumbnail.png"
        thumb = {"size": 128, "ocean": (238, 243, 248), "pad_raster": 0.1,
                 "pad_vector": 0.06, "basemap": None}
        bbox4326 = [-105.0, 39.0, -104.9, 39.1]
        # Bright sits south-west, dark sits north-east.
        bright_bbox = [-105.0, 39.0, -104.95, 39.05]
        dark_bbox = [-104.95, 39.05, -104.9, 39.1]
        tiles = [
            (bright_bbox, np.full((3, 8, 8), 200, "uint8")),
            (dark_bbox, np.full((3, 8, 8), 60, "uint8")),
        ]
        mosaic.make_thumbnail_mosaic(tiles, out, bbox4326, thumb)
        assert out.exists(), "thumbnail was not written"

        _, merc, w, h = thumbnails._thumb_grid(bbox4326, thumb["size"], thumb["pad_raster"])
        span_x = merc[2] - merc[0]
        span_y = merc[3] - merc[1]

        def _center_pixel(bbox: list[float]) -> tuple[int, int]:
            """The canvas pixel at a tile's own centre, by the same forward
            projection make_thumbnail_mosaic itself uses to place the tile."""
            cx, cy = thumbnails._to_merc((bbox[0] + bbox[2]) / 2, (bbox[1] + bbox[3]) / 2)
            col = int((cx - merc[0]) / span_x * w)
            row = int((merc[3] - cy) / span_y * h)
            return col, row

        bright_col, bright_row = _center_pixel(bright_bbox)
        dark_col, dark_row = _center_pixel(dark_bbox)

        with Image.open(out) as im:
            assert max(im.size) == 128, im.size
            rgb = im.convert("RGB")
            colors = {c for _, c in rgb.getcolors(maxcolors=1 << 16)}
            bright_px = rgb.getpixel((bright_col, bright_row))
            dark_px = rgb.getpixel((dark_col, dark_row))

        assert len(colors) > 1, "every pixel is one colour, no tiles were pasted"
        assert bright_px[0] > 150, (
            f"bright tile must read bright at its own centre, got {bright_px}")
        assert dark_px[0] < 100, f"dark tile must read dark at its own centre, got {dark_px}"


def check_thumbnail_mosaic_west_overhang() -> None:
    """A tile whose west edge falls off the canvas must paint its own
    correct sub-region there, not the sub-region the patch's own origin
    would give under an unclipped slice.

    A flat fill cannot tell these two sub-regions apart, since every pixel
    of a flat tile has the same value wherever it is sliced from. The tile
    here carries a west-to-east ramp instead, one distinct value per column,
    so only the true correct sub-region produces the expected value.
    """
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "thumbnail.png"
        thumb = {"size": 64, "ocean": (238, 243, 248), "pad_raster": 0.0,
                 "pad_vector": 0.06, "basemap": None}
        # The canvas covers lon -10 to 10. The tile covers lon -30 to 0, so
        # its western two thirds, lon -30 to -10, overhangs off canvas.
        bbox4326 = [-10.0, 0.0, 10.0, 20.0]
        tile_bbox = [-30.0, 0.0, 0.0, 20.0]
        ramp = np.tile(np.arange(256, dtype="uint8"), (3, 4, 1))
        mosaic.make_thumbnail_mosaic([(tile_bbox, ramp)], out, bbox4326, thumb)

        # Mercator x is a linear function of longitude, so the fraction along
        # the tile at the canvas west edge equals the plain longitude
        # fraction. The canvas west edge sits at bbox4326's own west edge,
        # since pad_raster is 0 here.
        fraction = (bbox4326[0] - tile_bbox[0]) / (tile_bbox[2] - tile_bbox[0])
        expected = 255 * fraction

        _, _, _, h = thumbnails._thumb_grid(bbox4326, thumb["size"], thumb["pad_raster"])
        with Image.open(out) as im:
            got = im.convert("RGB").getpixel((0, h // 2))[0]

        assert abs(got - expected) <= 20, (
            f"west overhang must read the ramp's own value near {expected}, got {got}")


if __name__ == "__main__":
    print("check_mosaic.py")
    check("fetch returns features", check_fetch_returns_features)
    check("fetch rejects an unconsumed next page", check_fetch_rejects_unconsumed_page)
    check("remote size comes from HEAD", check_remote_size)
    check("remote size handles 404", check_remote_size_handles_404)
    check("remote asset carries size and no checksum",
          check_remote_asset_has_size_and_no_checksum)
    check("read_overview yields bands and pixels", check_read_overview)
    check("read_overview rejects no overviews", check_read_overview_rejects_no_overviews)
    check("read_overview rejects unreadable input", check_read_overview_rejects_unreadable)
    check("build_items writes conforming items", check_build_items)
    check("build_items rejects a feature with no datetime",
          check_build_items_rejects_missing_datetime)
    check("build_items rejects a feature with no image asset",
          check_build_items_rejects_missing_image_asset)
    check("minimal.json carries only bbox and href", check_minimal_json)
    check("thumbnail mosaic pastes tiles", check_thumbnail_mosaic)
    check("thumbnail mosaic paints a west-overhanging tile's own sub-region",
          check_thumbnail_mosaic_west_overhang)
    if FAILURES:
        raise SystemExit(f"{len(FAILURES)} failure(s)")
    print("all ok")
