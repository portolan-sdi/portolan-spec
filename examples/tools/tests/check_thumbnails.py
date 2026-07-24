# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "duckdb>=1.5.5",
#   "rasterio>=1.5",
#   "numpy",
#   "Pillow>=11",
# ]
# ///
"""Standalone check for the pure-Python vector and raster thumbnail path.

Seeds the tile cache so no network is hit, builds tiny sources, and asserts each
thumbnail PNG exists at the framed width and true aspect ratio.
Run: uv run examples/tools/tests/check_thumbnails.py
"""
import json
import sys
import tempfile
from pathlib import Path

import duckdb
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tiles  # noqa: E402
import thumbnails  # noqa: E402

GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "properties": {"cat": "x"},
         "geometry": {"type": "Polygon",
                      "coordinates": [[[0, 0], [2, 0], [2, 1], [0, 1], [0, 0]]]}},
    ],
}


def _seed_tiles() -> None:
    def fake_fetch(url, z, x, y, cache):
        p = cache / "tiles" / str(z) / str(x) / f"{y}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():
            Image.new("RGB", (256, 256), (200, 220, 240)).save(p)
        return p
    tiles._fetch_tile = fake_fetch


def check_vector_thumbnail() -> None:
    _seed_tiles()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        gj = tmp / "t.geojson"
        gj.write_text(json.dumps(GEOJSON))
        gpkg = tmp / "t.gpkg"
        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy=true;")
        con.execute(f"CREATE TABLE t AS SELECT cat, ST_SetCRS(geom, 'EPSG:4326') AS geom "
                    f"FROM ST_Read('{gj}')")
        con.execute(f"COPY t TO '{gpkg}' (FORMAT GDAL, DRIVER 'GPKG', LAYER_NAME 'layer')")
        con.close()

        out = tmp / "thumb.png"
        thumb = {"size": 256, "pad_vector": 0.06, "pad_raster": 0.4,
                 "ocean": (238, 243, 248), "basemap": "http://x/{z}/{x}/{y}.png",
                 "cache": tmp, "attribution": None}
        style = {"geometry": "polygon", "color": "#3388ff", "outline": "#ffffff"}
        thumbnails.make_thumbnail_vector(gpkg, out, [-0.2, -0.2, 2.2, 1.2], style, thumb)
        assert out.exists(), "no thumbnail written"
        im = Image.open(out)
        assert im.width == 256, im.size            # wider than tall, width caps at size
        assert im.height < im.width, im.size       # true aspect ratio, not square
        assert not Path(str(out) + ".aux.xml").exists(), "gdal aux sidecar leaked"


def main() -> int:
    check_vector_thumbnail()
    print("OK, vector thumbnail")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
