"""Thumbnail rendering.

Renders previews in Web Mercator at the data's true aspect ratio over a CARTO
light XYZ tile basemap, painting features from the collection style block so the
preview mirrors the map.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import duckdb
import numpy as np
import rasterio.features
from rasterio.transform import from_bounds
from PIL import Image

import tiles
from common import _hex_rgb
from derivatives import _category_colors


_MERC_R = 6378137.0


def _to_merc(lon: float, lat: float) -> tuple[float, float]:
    lat = max(min(lat, 85.06), -85.06)
    return _MERC_R * math.radians(lon), _MERC_R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def _thumb_grid(bbox4326: list[float], size: int, pad: float) -> tuple[list[float], list[float], int, int]:
    """Pad the WGS84 bbox, clamp to the Mercator-valid range, and return the
    padded bbox, its Mercator extent, and a pixel size at the true aspect ratio."""
    minx, miny, maxx, maxy = bbox4326
    dx = (maxx - minx) or 1e-4
    dy = (maxy - miny) or 1e-4
    minx -= dx * pad; maxx += dx * pad
    miny -= dy * pad; maxy += dy * pad
    minx = max(minx, -180.0); maxx = min(maxx, 180.0)
    miny = max(miny, -85.06); maxy = min(maxy, 85.06)
    x0, y0 = _to_merc(minx, miny)
    x1, y1 = _to_merc(maxx, maxy)
    mdx = (x1 - x0) or 1.0
    mdy = (y1 - y0) or 1.0
    if mdx >= mdy:
        w, h = size, max(1, round(size * mdy / mdx))
    else:
        w, h = max(1, round(size * mdx / mdy)), size
    return [minx, miny, maxx, maxy], [x0, y0, x1, y1], w, h


def _merc_geom_sql(radius_m: float) -> str:
    """SQL expression that reprojects the WGS84 source geometry to EPSG:3857 and,
    for points, buffers it to `radius_m` so a raw point does not vanish to a
    single pixel at world scale."""
    g = "ST_Transform(geom, 'EPSG:4326', 'EPSG:3857', always_xy := true)"
    return f"ST_Buffer({g}, {radius_m})" if radius_m else g


def _clip_where(bbox4326: list[float]) -> str:
    minx, miny, maxx, maxy = bbox4326
    env = f"ST_MakeEnvelope({minx}, {miny}, {maxx}, {maxy})"
    return f"ST_Intersects(geom, {env})"


def _mercator_geoms(src: Path, bbox4326: list[float], geometry: str,
                    radius_m: float, field: str | None):
    """Read the WGS84 source, clip to the padded bbox, reproject to EPSG:3857,
    and return `(features, outlines)`. `features` is `(geojson_dict, field_value)`
    pairs, points already buffered. `outlines` is polygon boundary geojson dicts,
    empty for non-polygon geometry."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy=true;")
    read = f"ST_Read('{src}')"
    g = _merc_geom_sql(radius_m if geometry == "point" else 0.0)
    where = _clip_where(bbox4326)
    sel_field = f', "{field}"' if field else ""
    rows = con.execute(
        f"SELECT ST_AsGeoJSON({g}) AS gj{sel_field} FROM {read} WHERE {where}"
    ).fetchall()
    features = [(json.loads(r[0]), (r[1] if field else None)) for r in rows if r[0]]
    outlines = []
    if geometry == "polygon":
        merc = _merc_geom_sql(0.0)
        orows = con.execute(
            f"SELECT ST_AsGeoJSON(ST_Boundary({merc})) AS gj FROM {read} WHERE {where}"
        ).fetchall()
        outlines = [json.loads(r[0]) for r in orows if r[0]]
    con.close()
    return features, outlines


def _feature_count(src: Path, bbox4326: list[float]) -> int:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy=true;")
    n = con.execute(
        f"SELECT count(*) FROM ST_Read('{src}') WHERE {_clip_where(bbox4326)}"
    ).fetchone()[0]
    con.close()
    return int(n)


def _make_canvas_arr(thumb: dict, merc: list[float], w: int, h: int) -> np.ndarray:
    """Return the `(h, w, 3)` uint8 base canvas, the fetched basemap or a flat
    ocean fill when no basemap is configured."""
    if thumb.get("basemap"):
        return tiles.fetch_basemap(thumb["basemap"], merc, w, h, thumb["cache"])
    canvas = np.empty((h, w, 3), dtype=np.uint8)
    canvas[:] = thumb["ocean"]
    return canvas


def _burn(canvas: np.ndarray, geoms: list[dict], rgb: tuple[int, int, int],
          transform, w: int, h: int) -> None:
    """Rasterize GeoJSON geometries (EPSG:3857) onto the canvas in `rgb`."""
    if not geoms:
        return
    mask = rasterio.features.rasterize(
        [(g, 1) for g in geoms], out_shape=(h, w), transform=transform,
        fill=0, all_touched=False, dtype="uint8")
    canvas[mask == 1] = rgb


def make_thumbnail_vector(vector_src: Path, out_png: Path, bbox4326: list[float],
                          style: dict, thumb: dict) -> None:
    """Paint the features over the basemap using the collection `style` block. A
    categorical field colours by category from the shared palette, otherwise the
    default colour fills flat. Polygons get a thin outline for granularity."""
    b, merc, w, h = _thumb_grid(bbox4326, thumb["size"], thumb["pad_vector"])
    canvas = _make_canvas_arr(thumb, merc, w, h)
    transform = from_bounds(merc[0], merc[1], merc[2], merc[3], w, h)
    geometry = style.get("geometry", "polygon")
    if _feature_count(vector_src, b):
        radius_m = (merc[2] - merc[0]) / w * 2.5
        field = style.get("category_field")
        feats, outlines = _mercator_geoms(vector_src, b, geometry, radius_m, field)
        if field:
            colors = dict(_category_colors(vector_src, field, style.get("palette")))
            for gjson, val in feats:
                rgb = colors.get(val)
                if rgb:
                    _burn(canvas, [gjson], _hex_rgb(rgb), transform, w, h)
        else:
            _burn(canvas, [g for g, _ in feats], _hex_rgb(style.get("color", "#3388ff")),
                  transform, w, h)
        if geometry == "polygon":
            _burn(canvas, outlines, _hex_rgb(style.get("outline", "#ffffff")),
                  transform, w, h)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(canvas).save(out_png)


def make_thumbnail_raster(tif: Path, out_png: Path, bbox4326: list[float],
                          thumb: dict) -> None:
    """Warp the raster into the Web Mercator canvas over the basemap, treating 0
    as transparent nodata, then alpha-over composite and write the PNG."""
    import rasterio
    from rasterio.warp import reproject, Resampling

    b, merc, w, h = _thumb_grid(bbox4326, thumb["size"], thumb["pad_raster"])
    canvas = _make_canvas_arr(thumb, merc, w, h).astype(np.uint8)
    transform = from_bounds(merc[0], merc[1], merc[2], merc[3], w, h)
    with rasterio.open(tif) as src:
        bands = min(src.count, 3)
        dest = np.zeros((bands, h, w), dtype="uint8")
        for i in range(bands):
            reproject(
                source=rasterio.band(src, i + 1), destination=dest[i],
                src_transform=src.transform, src_crs=src.crs,
                dst_transform=transform, dst_crs="EPSG:3857",
                src_nodata=0, dst_nodata=0, resampling=Resampling.bilinear)
    overlay = np.moveaxis(dest, 0, -1)  # (h, w, bands)
    if bands == 1:
        overlay = np.repeat(overlay, 3, axis=-1)
    mask = (overlay.sum(axis=-1) > 0)
    canvas[mask] = overlay[mask][:, :3]
    out_png.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(canvas).save(out_png)


def build_thumb_ctx(manifest: dict, cache: Path) -> dict:
    """Read the manifest thumbnails block into the shared thumbnail context.
    Everything thumbnail-specific lives in the manifest, not here. The basemap is
    an XYZ tile template (`{z}/{x}/{y}`), CARTO light by default, passed straight
    through to the tile fetcher."""
    t = manifest.get("thumbnails", {}) or {}
    bm = t.get("basemap")
    basemap = None
    attribution = None
    if bm:
        basemap = bm["url"] if isinstance(bm, dict) else bm
        attribution = bm.get("attribution") if isinstance(bm, dict) else None
    return {
        "size": int(t.get("size", 768)),
        "pad_vector": float(t.get("pad_vector", 0.06)),
        "pad_raster": float(t.get("pad_raster", 0.4)),
        "ocean": _hex_rgb(t.get("ocean_color", "#eef3f8")),
        "basemap": basemap,
        "cache": cache,
        "attribution": attribution,
    }


def _thumb_desc(thumb: dict) -> str:
    if thumb.get("attribution"):
        return f"Preview thumbnail over a light basemap. {thumb['attribution']}."
    return "Preview thumbnail"
