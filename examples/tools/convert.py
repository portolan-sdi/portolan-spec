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
from crs import assert_known_crs, detect_vector_crs
from fetch import _prepare_ogr_source


def write_web_geoparquet(norm: Path, out_parquet: Path) -> None:
    """Write the canonical vector asset as a web-optimized GeoParquet 2.0 file.

    Delegates to geoparquet-io's web profile, the ecosystem's canonical writer
    and the only one that emits both native 2.0 GeospatialStatistics and a
    Parquet page index. The profile gives us a native geometry type, per row
    group statistics, a retained covering bbox column for page-level pruning,
    the page index, Hilbert spatial ordering, byte-targeted fetch-sized row
    groups, and ZSTD compression. `norm` here is the canonical output-CRS
    GeoPackage, and geoparquet-io preserves whatever CRS it is given, so the
    Parquet keeps the source CRS by default rather than being forced to
    EPSG:4326."""
    from geoparquet_io import convert_geoparquet

    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    out_parquet.unlink(missing_ok=True)
    convert_geoparquet(str(norm), str(out_parquet),
                       optimize_for="web", compression_level=15)


# ------------------------------------------------------------------ conversions
def to_geoparquet(local: Path, spec_source: dict, out_parquet: Path,
                  output_crs: str | None) -> tuple[list[float], int, Path, str]:
    """Convert a vector source to the canonical web-optimized GeoParquet 2.0 file
    in its source CRS, or in `output_crs` when set, and return the WGS84 bbox, the
    feature count, the WGS84 GeoPackage intermediate, and the CRS actually written.

    A WGS84 GeoPackage (`norm`) is always produced for the bbox, the PMTiles feed,
    the thumbnail, and style sampling. The canonical asset is built in the output
    CRS with DuckDB, then handed to geoparquet-io's web profile, which preserves
    the CRS. Every geometry write is wrapped in ST_SetCRS so the output CRS is
    tagged, and sources that already carry a `fid` column keep its real values
    through an OGC_FID round-trip rather than getting a resequenced fid.

    Returns (bbox_wgs84, count, norm, canonical_crs). The caller keeps `norm`, the
    EPSG:4326 GeoPackage, to build derivatives (PMTiles, thumbnail, style
    sampling), then deletes it."""
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    extract_dir = out_parquet.with_suffix(".src")
    src, layer = _prepare_ogr_source(local, spec_source, extract_dir)
    source_crs = detect_vector_crs(src, layer)
    out_crs = output_crs or source_crs
    if output_crs:
        assert_known_crs(output_crs)

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy=true;")
    read = f"ST_Read('{src}'" + (f", layer='{layer}'" if layer else "") + ")"

    cols = [r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {read}").fetchall()]
    has_fid = any(c.lower() == "fid" for c in cols)

    if out_crs == source_crs:
        canon_geom = f"ST_SetCRS(geom, '{source_crs}')"
    else:
        canon_geom = (f"ST_SetCRS(ST_Transform(geom, '{source_crs}', '{out_crs}'), "
                      f"'{out_crs}')")
    norm_geom = (f"ST_SetCRS(ST_Transform(geom, '{source_crs}', 'EPSG:4326'), "
                 f"'EPSG:4326')")

    def write_gpkg(table: str, geom_expr: str, path: Path, alias: str) -> None:
        path.unlink(missing_ok=True)
        if has_fid:
            con.execute(f"CREATE TABLE {table} AS SELECT fid AS OGC_FID, "
                        f"* EXCLUDE (fid, geom), {geom_expr} AS geom FROM {read}")
            con.execute(f"COPY {table} TO '{path}' (FORMAT GDAL, DRIVER 'GPKG', "
                        f"LAYER_NAME 'layer', LAYER_CREATION_OPTIONS 'FID=OGC_FID')")
            con.execute("INSTALL sqlite; LOAD sqlite;")
            con.execute(f"ATTACH '{path}' AS {alias} (TYPE SQLITE)")
            con.execute(f'ALTER TABLE {alias}.layer RENAME COLUMN "OGC_FID" TO "fid"')
            con.execute(f"DETACH {alias}")
        else:
            con.execute(f"CREATE TABLE {table} AS "
                        f"SELECT * REPLACE ({geom_expr} AS geom) FROM {read}")
            con.execute(f"COPY {table} TO '{path}' "
                        f"(FORMAT GDAL, DRIVER 'GPKG', LAYER_NAME 'layer')")

    canon = out_parquet.with_suffix(".canon.gpkg")
    norm = out_parquet.with_suffix(".norm.gpkg")
    write_gpkg("canon_src", canon_geom, canon, "gcanon")
    write_gpkg("norm_src", norm_geom, norm, "gnorm")

    minx, miny, maxx, maxy, n = con.execute(
        "SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e), c "
        "FROM (SELECT ST_Extent(ST_Union_Agg(geom)) e, count(*) c FROM norm_src)"
    ).fetchone()
    con.close()

    write_web_geoparquet(canon, out_parquet)
    canon.unlink(missing_ok=True)
    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    return [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)], int(n), norm, out_crs


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
