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
    con.execute("INSTALL spatial; LOAD spatial;")
    layers = con.execute("SELECT layers FROM ST_Read_Meta(?)", [gdal_path]).fetchone()[0]
    con.close()
    chosen = None
    if layer:
        chosen = next((l for l in layers if l["name"] == layer), None)
    chosen = chosen or (layers[0] if layers else None)
    if not chosen or not chosen["geometry_fields"]:
        raise ValueError(f"{gdal_path} has no readable geometry layer")
    crs = chosen["geometry_fields"][0].get("crs") or {}
    out = _crs_string(crs.get("auth_name"), crs.get("auth_code"))
    if not out:
        raise ValueError(f"{gdal_path} layer {chosen['name']} declares no CRS")
    return out
