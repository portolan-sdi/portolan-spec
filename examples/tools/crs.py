"""Coordinate reference system detection and resolution.

Detects the true source CRS of each geospatial source and resolves the output
CRS, which preserves the source by default and is overridable per manifest or
per collection. Nothing about the CRS is hardcoded in the rest of the generator.
"""
from __future__ import annotations

from pathlib import Path

import duckdb


def _crs_string(auth: str | None, code: str | None) -> str | None:
    if auth and code:
        return f"{auth}:{code}"
    return None


def detect_raster_crs(tif: Path) -> str:
    """Return the raster CRS as `EPSG:<code>` via rasterio, raising if absent."""
    import rasterio

    with rasterio.open(tif) as ds:
        if ds.crs is None:
            raise ValueError(f"{tif} declares no CRS")
        epsg = ds.crs.to_epsg()
        if epsg is None:
            raise ValueError(f"{tif} CRS has no EPSG code: {ds.crs}")
        return f"EPSG:{epsg}"


def detect_vector_crs(gdal_path: str, layer: str | None) -> str:
    """Return the source CRS of a GDAL-readable vector as `EPSG:<code>`.

    Reads the per-layer spatial reference with DuckDB `ST_Read_Meta`. Raises if
    the target layer declares no CRS, so a missing projection never passes
    silently."""
    con = duckdb.connect()
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
        layers = con.execute("SELECT layers FROM ST_Read_Meta(?)", [gdal_path]).fetchone()[0]
    finally:
        con.close()
    chosen = None
    if layer:
        chosen = next((l for l in layers if l["name"] == layer), None)
    chosen = chosen or (layers[0] if layers else None)
    if not chosen or not chosen["geometry_fields"]:
        raise ValueError(f"{gdal_path} has no readable geometry layer")
    crs = chosen["geometry_fields"][0].get("crs") or {}
    auth_name = crs.get("auth_name")
    out = _crs_string(auth_name, crs.get("auth_code"))
    if not out:
        raise ValueError(f"{gdal_path} layer {chosen['name']} declares no CRS")
    if auth_name.upper() != "EPSG":
        raise ValueError(
            f"{gdal_path} layer {chosen['name']} uses unsupported authority "
            f"{auth_name!r} (only EPSG is supported)")
    return out


def resolve_output_crs(spec: dict, manifest_output_crs: str | None) -> str | None:
    """Resolve the configured output CRS. Per-collection wins, then the manifest
    default, then None which means preserve the detected source CRS."""
    return spec.get("output_crs") or manifest_output_crs


def assert_known_crs(crs: str) -> None:
    """Raise if DuckDB cannot resolve the CRS, so a typo in the manifest fails
    the build early instead of producing a broken transform."""
    con = duckdb.connect()
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
        ok = con.execute(
            "SELECT count(*) FROM duckdb_coordinate_systems() WHERE auth_name || ':' || auth_code = ?",
            [crs]).fetchone()[0]
    finally:
        con.close()
    if not ok:
        raise ValueError(f"unknown output_crs {crs}")
