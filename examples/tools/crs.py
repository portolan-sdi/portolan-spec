"""Coordinate reference system detection and resolution.

Detects the true source CRS of each geospatial source and resolves the output
CRS, which preserves the source by default and is overridable per manifest or
per collection. Nothing about the CRS is hardcoded in the rest of the generator.
"""
from __future__ import annotations

import json
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


# PROJJSON names a CRS by type. Only the two horizontal kinds the generator can
# produce are mapped, so a compound or vertical CRS raises rather than being
# described with prose that would not be true of it.
_CRS_KINDS = {"GeographicCRS": "geographic", "ProjectedCRS": "projected"}

_DESCRIBED: dict[str, dict] = {}


def describe_crs(crs: str) -> dict:
    """Return `{code, name, kind, unit}` for an `AUTH:CODE` string.

    `kind` is `geographic` or `projected` and `unit` is the axis unit, both read
    out of the PROJJSON DuckDB holds for the CRS rather than inferred from the
    code. That keeps the generated CRS prose true for whatever CRS a Collection
    happens to preserve, instead of true only for the ones someone thought of.
    Raises if DuckDB cannot resolve the CRS or the CRS is not a horizontal one.
    Results are memoized, the lookup costs a DuckDB connection."""
    if crs in _DESCRIBED:
        return _DESCRIBED[crs]
    auth, _, code = crs.partition(":")
    con = duckdb.connect()
    try:
        con.execute("INSTALL spatial; LOAD spatial;")
        row = con.execute(
            "SELECT projjson FROM duckdb_coordinate_systems() "
            "WHERE auth_name = ? AND auth_code = ?", [auth, code]).fetchone()
    finally:
        con.close()
    if not row:
        raise ValueError(f"unknown CRS {crs}")
    pj = json.loads(row[0])
    kind = _CRS_KINDS.get(pj.get("type"))
    if not kind:
        raise ValueError(f"{crs} is a {pj.get('type')}, not a horizontal CRS")
    axes = pj.get("coordinate_system", {}).get("axis") or []
    unit = axes[0].get("unit") if axes else None
    # PROJJSON writes a unit either as a bare name or as an object when it
    # carries a conversion factor, for example a US survey foot.
    if isinstance(unit, dict):
        unit = unit.get("name")
    if not unit:
        raise ValueError(f"{crs} declares no axis unit")
    out = {"code": crs, "name": pj.get("name") or crs, "kind": kind, "unit": unit}
    _DESCRIBED[crs] = out
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
