"""Convert each source to its cloud-native canonical asset.

Vector to web-optimized GeoParquet 2.0, raster to COG with embedded band
statistics, tabular CSV to plain Parquet. Also reads back columns and counts.
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

import duckdb

from common import run
from config import GDAL_DTYPE
from fetch import _prepare_ogr_source


def write_web_geoparquet(norm: Path, out_parquet: Path) -> None:
    """Write the canonical vector asset as a web-optimized GeoParquet 2.0 file.

    Delegates to geoparquet-io's web profile, the ecosystem's canonical writer
    and the only one that emits both native 2.0 GeospatialStatistics and a
    Parquet page index. The profile gives us a native geometry type, per row
    group statistics, a retained covering bbox column for page-level pruning,
    the page index, Hilbert spatial ordering, byte-targeted fetch-sized row
    groups, and ZSTD compression. `norm` must already be EPSG:4326."""
    from geoparquet_io import convert_geoparquet

    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    out_parquet.unlink(missing_ok=True)
    convert_geoparquet(str(norm), str(out_parquet),
                       optimize_for="web", compression_level=15)


# ------------------------------------------------------------------ conversions
def to_geoparquet(local: Path, spec_source: dict, out_parquet: Path) -> tuple[list[float], int, Path]:
    """Normalize the source to EPSG:4326 with ogr2ogr into a GeoPackage, compute
    the bbox and feature count from it, then write the canonical asset as a
    web-optimized GeoParquet 2.0 file (see write_web_geoparquet).

    Returns (bbox, count, norm). The caller keeps `norm`, the EPSG:4326
    GeoPackage, to build derivatives (PMTiles, thumbnail, style sampling) that
    read it rather than the native 2.0 output, then deletes it."""
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    extract_dir = out_parquet.with_suffix(".src")
    src, layer = _prepare_ogr_source(local, spec_source, extract_dir)
    norm = out_parquet.with_suffix(".norm.gpkg")
    norm.unlink(missing_ok=True)
    cmd = ["ogr2ogr", "-t_srs", "EPSG:4326", "-f", "GPKG", "-nln", "layer", str(norm), src]
    if layer:
        cmd.append(layer)
    run(cmd)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    minx, miny, maxx, maxy, n = con.execute(f"""
        SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e), c
        FROM (SELECT ST_Extent(ST_Union_Agg(geom)) e, count(*) c FROM ST_Read('{norm}'))
    """).fetchone()
    con.close()
    write_web_geoparquet(norm, out_parquet)
    if extract_dir.exists():
        import shutil
        shutil.rmtree(extract_dir)
    return [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)], int(n), norm


def feature_count(parquet: Path) -> int:
    con = duckdb.connect()
    n = con.execute(f"SELECT count(*) FROM read_parquet('{parquet}')").fetchone()[0]
    con.close()
    return int(n)


def to_cog(src_tif: Path, out_tif: Path) -> None:
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    run(["gdal_translate", "-of", "COG", "-co", "COMPRESS=DEFLATE",
         "-co", "STATISTICS=YES", str(src_tif), str(out_tif)])


def _gdalinfo(tif: Path) -> dict:
    return json.loads(run(["gdalinfo", "-json", "-stats", str(tif)]).stdout)


def bands_from_cog(tif: Path) -> list[dict]:
    info = _gdalinfo(tif)
    out = []
    for b in info["bands"]:
        meta = b.get("metadata", {}).get("", {})
        stats = {}
        for key, name in [("STATISTICS_MINIMUM", "minimum"), ("STATISTICS_MAXIMUM", "maximum"),
                          ("STATISTICS_MEAN", "mean"), ("STATISTICS_STDDEV", "stddev")]:
            if key in meta:
                stats[name] = round(float(meta[key]), 4)
        band: dict[str, Any] = {"data_type": GDAL_DTYPE.get(b.get("type", ""), "other")}
        if stats:
            band["statistics"] = stats
        out.append(band)
    return out


def proj_code(tif: Path) -> str:
    wkt = _gdalinfo(tif).get("coordinateSystem", {}).get("wkt", "")
    ids = re.findall(r'ID\["EPSG",(\d+)\]', wkt)
    return f"EPSG:{ids[-1]}" if ids else ""


def bbox_wgs84_raster(tif: Path) -> list[float]:
    ext = _gdalinfo(tif)["wgs84Extent"]["coordinates"][0]
    xs = [p[0] for p in ext]
    ys = [p[1] for p in ext]
    return [round(min(xs), 6), round(min(ys), 6), round(max(xs), 6), round(max(ys), 6)]


def to_table_parquet(csv: Path, out_parquet: Path) -> None:
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"""
        COPY (SELECT * FROM read_csv_auto('{csv}', sample_size=-1, all_varchar=false))
        TO '{out_parquet}' (FORMAT PARQUET, COMPRESSION zstd);
    """)
    con.close()


def table_columns(parquet: Path) -> list[dict]:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{parquet}')").fetchall()
    con.close()
    return [{"name": r[0], "type": r[1].lower()} for r in rows]
