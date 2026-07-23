# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.3",
#   "duckdb>=1.5.4",
#   "jsonschema>=4.26.0",
#   "pyarrow>=24",
#   "geoparquet-io @ git+https://github.com/yharby/geoparquet-io.git@f27e53108910f19bd74a9ff4be5c7d97b104753c",
#   "rasterio>=1.4",
# ]
# ///
"""Standalone check for convert.write_web_geoparquet.

Builds a tiny EPSG:4326 GeoPackage with ogr2ogr, runs the wrapper, and asserts
the output is native GeoParquet 2.0 with a covering bbox column and a page index.
Run: uv run examples/tools/tests/check_web_output.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert import write_web_geoparquet  # noqa: E402

import pyarrow.parquet as pq  # noqa: E402

GEOJSON = {
    "type": "FeatureCollection",
    "features": [
        {"type": "Feature", "properties": {"name": "a"},
         "geometry": {"type": "Polygon",
                      "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}},
        {"type": "Feature", "properties": {"name": "b"},
         "geometry": {"type": "Polygon",
                      "coordinates": [[[2, 2], [3, 2], [3, 3], [2, 3], [2, 2]]]}},
    ],
}


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        gj = tmp / "tiny.geojson"
        gj.write_text(json.dumps(GEOJSON))
        norm = tmp / "tiny.gpkg"
        subprocess.run(
            ["ogr2ogr", "-t_srs", "EPSG:4326", "-f", "GPKG", "-nln", "layer",
             str(norm), str(gj)], check=True)

        out = tmp / "tiny.parquet"
        write_web_geoparquet(norm, out)

        pf = pq.ParquetFile(out)
        schema = pf.schema_arrow
        geo = json.loads((schema.metadata or {})[b"geo"])
        assert geo["version"].startswith("2."), f"not 2.0: {geo['version']}"
        assert "bbox" in schema.names, f"no covering bbox column: {schema.names}"
        gcol = next(iter(geo["columns"].values()))
        assert "covering" in gcol, "covering not advertised in geo metadata"
        col0 = pf.metadata.row_group(0).column(0)
        assert col0.has_column_index and col0.has_offset_index, "no page index"
        assert "geom" in schema.names, f"no geometry column: {schema.names}"
    print("OK, native 2.0, covering bbox, page index")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
