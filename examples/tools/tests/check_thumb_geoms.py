# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "duckdb>=1.5.5",
# ]
# ///
"""Standalone check for thumbnails._mercator_geoms.

Builds a tiny EPSG:4326 GeoPackage with DuckDB and asserts the extracted
geometry is reprojected to EPSG:3857 meters and clipped to the bbox.
Run: uv run examples/tools/tests/check_thumb_geoms.py
"""
import json
import sys
import tempfile
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import thumbnails  # noqa: E402

GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "properties": {"cat": "x"},
         "geometry": {"type": "Polygon",
                      "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}},
    ],
}


def main() -> int:
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

        bbox = [-1.0, -1.0, 2.0, 2.0]
        feats, outlines = thumbnails._mercator_geoms(gpkg, bbox, "polygon", 0.0, "cat")
        assert len(feats) == 1, feats
        gjson, val = feats[0]
        assert val == "x", val
        # EPSG:3857 puts the ~1 degree polygon at ~1e5 metres, not degrees.
        xs = [pt[0] for ring in gjson["coordinates"] for pt in ring]
        assert max(abs(x) for x in xs) > 1000.0, "geometry not in Mercator metres"
        assert len(outlines) == 1, outlines
        n = thumbnails._feature_count(gpkg, bbox)
        assert n == 1, n
    print("OK, mercator geoms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
