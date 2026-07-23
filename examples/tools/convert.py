"""Convert each source to its cloud-native canonical asset.

Vector to web-optimized GeoParquet 2.0, raster to COG with embedded band
statistics, tabular CSV to plain Parquet. Also reads back columns and counts.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import duckdb

from crs import assert_known_crs, detect_raster_crs, detect_vector_crs
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
    # A feature-id column arrives either as a real `fid` (e.g. a GeoPackage) or as
    # the OGR-reserved `OGC_FID` that ST_Read surfaces for formats without an
    # explicit one (e.g. Shapefiles). Either way route it through the OGC_FID
    # round-trip so GDAL writes it as the feature id, never a plain attribute
    # column, which the GPKG Arrow writer refuses for the reserved name.
    fid_col = next((c for c in cols if c.lower() in ("fid", "ogc_fid")), None)

    if out_crs == source_crs:
        canon_geom = f"ST_SetCRS(geom, '{source_crs}')"
    else:
        canon_geom = (f"ST_SetCRS(ST_Transform(geom, '{source_crs}', '{out_crs}'), "
                      f"'{out_crs}')")
    norm_geom = (f"ST_SetCRS(ST_Transform(geom, '{source_crs}', 'EPSG:4326'), "
                 f"'EPSG:4326')")

    def write_gpkg(table: str, geom_expr: str, path: Path, alias: str) -> None:
        path.unlink(missing_ok=True)
        if fid_col:
            con.execute(f'CREATE TABLE {table} AS SELECT "{fid_col}" AS OGC_FID, '
                        f'* EXCLUDE ("{fid_col}", geom), {geom_expr} AS geom FROM {read}')
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


def to_cog(src_tif: Path, out_tif: Path, output_crs: str | None) -> str:
    """Write a Cloud Optimized GeoTIFF, preserving the source CRS by default or
    warping to `output_crs` when set. Returns the CRS actually written."""
    import numpy as np  # noqa
    import rasterio
    from rasterio.warp import calculate_default_transform, reproject, Resampling

    out_tif.parent.mkdir(parents=True, exist_ok=True)
    source_crs = detect_raster_crs(src_tif)
    out_crs = output_crs or source_crs
    if output_crs:
        assert_known_crs(output_crs)
    cog_profile = {"driver": "COG", "compress": "DEFLATE"}
    with rasterio.open(src_tif) as src:
        if out_crs == source_crs:
            data = src.read()
            profile = src.profile.copy()
            profile.update(cog_profile)
            with rasterio.open(out_tif, "w", **profile) as dst:
                dst.write(data)
                dst.build_overviews([2, 4, 8], Resampling.average)
        else:
            transform, width, height = calculate_default_transform(
                src.crs, out_crs, src.width, src.height, *src.bounds)
            profile = src.profile.copy()
            profile.update(cog_profile)
            profile.update(crs=out_crs, transform=transform, width=width, height=height)
            with rasterio.open(out_tif, "w", **profile) as dst:
                for i in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, i), destination=rasterio.band(dst, i),
                        src_transform=src.transform, src_crs=src.crs,
                        dst_transform=transform, dst_crs=out_crs, resampling=Resampling.bilinear)
                dst.build_overviews([2, 4, 8], Resampling.average)
    return out_crs


def bands_from_cog(tif: Path) -> list[dict]:
    """Per-band data type and statistics from the COG, kept in STAC 1.1 core bands."""
    import numpy as np
    import rasterio

    out = []
    with rasterio.open(tif) as ds:
        for i in range(1, ds.count + 1):
            arr = ds.read(i, masked=True)
            band: dict = {"data_type": str(ds.dtypes[i - 1])}
            if arr.count():
                band["statistics"] = {
                    "minimum": round(float(arr.min()), 4), "maximum": round(float(arr.max()), 4),
                    "mean": round(float(arr.mean()), 4), "stddev": round(float(arr.std()), 4)}
            out.append(band)
    return out


def proj_code(tif: Path) -> str:
    import rasterio

    with rasterio.open(tif) as ds:
        epsg = ds.crs.to_epsg() if ds.crs else None
    return f"EPSG:{epsg}" if epsg else ""


def bbox_wgs84_raster(tif: Path) -> list[float]:
    import rasterio
    from rasterio.warp import transform_bounds

    with rasterio.open(tif) as ds:
        minx, miny, maxx, maxy = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds)
    return [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)]


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
