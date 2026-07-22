"""Thumbnail rendering.

Renders previews in Web Mercator at the data's true aspect ratio over a CARTO
light XYZ tile basemap, painting features from the collection style block so the
preview mirrors the map.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from common import run, _hex_rgb, _sql_lit
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


def _ogr_count(src: Path) -> int:
    out = json.loads(run(["ogrinfo", "-so", "-json", str(src)]).stdout)
    return sum(int(l.get("featureCount", 0) or 0) for l in out.get("layers", []))


def _tile_basemap_xml(url: str, cache: Path) -> Path:
    """Write a GDAL WMS TMS descriptor for an XYZ raster basemap (CARTO light by
    default). gdalwarp then reads it like any raster, fetching only the tiles the
    thumbnail extent needs at the zoom that matches the output resolution, and
    caching them on disk so repeat builds do not refetch."""
    tiles = cache / "tiles"
    tiles.mkdir(parents=True, exist_ok=True)
    xml = cache / "basemap.xml"
    xml.write_text(
        "<GDAL_WMS>\n"
        '  <Service name="TMS">\n'
        f"    <ServerUrl>{url}</ServerUrl>\n"
        "  </Service>\n"
        "  <DataWindow>\n"
        "    <UpperLeftX>-20037508.342789244</UpperLeftX>\n"
        "    <UpperLeftY>20037508.342789244</UpperLeftY>\n"
        "    <LowerRightX>20037508.342789244</LowerRightX>\n"
        "    <LowerRightY>-20037508.342789244</LowerRightY>\n"
        "    <TileLevel>18</TileLevel>\n"
        "    <TileCountX>1</TileCountX>\n"
        "    <TileCountY>1</TileCountY>\n"
        "    <YOrigin>top</YOrigin>\n"
        "  </DataWindow>\n"
        "  <Projection>EPSG:3857</Projection>\n"
        "  <BlockSizeX>256</BlockSizeX>\n"
        "  <BlockSizeY>256</BlockSizeY>\n"
        "  <BandsCount>3</BandsCount>\n"
        "  <UserAgent>portolan-reference/0.1</UserAgent>\n"
        f"  <Cache><Path>{tiles}</Path></Cache>\n"
        "</GDAL_WMS>\n"
    )
    return xml


def _make_canvas(canvas: Path, thumb: dict, merc: list[float], w: int, h: int) -> None:
    """Build the Mercator canvas, the CARTO tile basemap warped to the framed
    extent, or a flat ocean fill when no basemap is configured."""
    x0, y0, x1, y1 = merc
    canvas.unlink(missing_ok=True)
    if thumb.get("basemap"):
        run(["gdalwarp", "-q", "-of", "GTiff", "-t_srs", "EPSG:3857",
             "-te", str(x0), str(y0), str(x1), str(y1), "-ts", str(w), str(h),
             "-r", "bilinear", str(thumb["basemap"]), str(canvas)])
    else:
        ocean = thumb["ocean"]
        run(["gdal_create", "-of", "GTiff", "-bands", "3", "-outsize", str(w), str(h),
             "-a_srs", "EPSG:3857", "-a_ullr", str(x0), str(y1), str(x1), str(y0),
             "-burn", str(ocean[0]), "-burn", str(ocean[1]), "-burn", str(ocean[2]), str(canvas)])


def _clip_to_canvas(src: Path, bbox4326: list[float], gpkg: Path) -> int:
    """Reproject and clip a vector source into a Mercator GeoPackage. Clipping to
    the padded bbox also keeps sub-85-degree geometry finite. Returns feature count."""
    minx, miny, maxx, maxy = bbox4326
    gpkg.unlink(missing_ok=True)
    run(["ogr2ogr", "-t_srs", "EPSG:3857", "-clipsrc", str(minx), str(miny), str(maxx), str(maxy),
         "-nln", "layer", "-f", "GPKG", str(gpkg), str(src)])
    return _ogr_count(gpkg)


def _rasterize(canvas: Path, gpkg: Path, rgb: tuple[int, int, int], where: str | None = None) -> None:
    cmd = ["gdal_rasterize", "-l", "layer", "-b", "1", "-b", "2", "-b", "3",
           "-burn", str(rgb[0]), "-burn", str(rgb[1]), "-burn", str(rgb[2])]
    if where:
        cmd += ["-where", where]
    cmd += [str(gpkg), str(canvas)]
    run(cmd)


def _buffer_points(gpkg: Path, radius_m: float, keep_field: str | None) -> Path:
    """Grow point features into small circles so they read as visible dots.
    gdal_rasterize paints a raw point as a single pixel, which vanishes at world
    scale. The radius is passed in metres, sized from the pixel resolution, so
    dots stay the same on-screen size at any extent. Any category field is kept
    so per-category colouring still works."""
    out = gpkg.with_suffix(".buf.gpkg")
    out.unlink(missing_ok=True)
    cols = f', "{keep_field}"' if keep_field else ""
    run(["ogr2ogr", "-f", "GPKG", "-dialect", "SQLITE", "-nln", "layer",
         "-sql", f"SELECT ST_Buffer(geom, {radius_m}) AS geom{cols} FROM layer", str(out), str(gpkg)])
    return out


def _burn_outline(canvas: Path, gpkg: Path, rgb: tuple[int, int, int]) -> None:
    """Overlay polygon boundaries as thin lines so neighbouring features stay
    distinct even when they share a categorical colour (counties within a state)."""
    lines = gpkg.with_suffix(".lines.gpkg")
    lines.unlink(missing_ok=True)
    run(["ogr2ogr", "-f", "GPKG", "-dialect", "SQLITE", "-nln", "layer",
         "-sql", "SELECT ST_Boundary(geom) AS geom FROM layer", str(lines), str(gpkg)])
    if _ogr_count(lines):
        _rasterize(canvas, lines, rgb)
    lines.unlink(missing_ok=True)


def make_thumbnail_vector(vector_src: Path, out_png: Path, bbox4326: list[float],
                          style: dict, thumb: dict) -> None:
    """Paint the features over the basemap using the collection `style` block. A
    categorical field colours by category from the shared palette, otherwise the
    default colour fills flat. Polygons get a thin outline for granularity."""
    b, merc, w, h = _thumb_grid(bbox4326, thumb["size"], thumb["pad_vector"])
    canvas = out_png.with_suffix(".canvas.tif")
    _make_canvas(canvas, thumb, merc, w, h)
    gpkg = canvas.with_suffix(".feat.gpkg")
    if _clip_to_canvas(vector_src, b, gpkg):
        field = style.get("category_field")
        if style.get("geometry", "polygon") == "point":
            radius_m = (merc[2] - merc[0]) / w * 2.5
            buf = _buffer_points(gpkg, radius_m, field)
            gpkg.unlink(missing_ok=True)
            gpkg = buf
        if field:
            for val, hexc in _category_colors(vector_src, field, style.get("palette")):
                _rasterize(canvas, gpkg, _hex_rgb(hexc), where=f'"{field}" = {_sql_lit(val)}')
        else:
            _rasterize(canvas, gpkg, _hex_rgb(style.get("color", "#3388ff")))
        if style.get("geometry", "polygon") == "polygon":
            _burn_outline(canvas, gpkg, _hex_rgb(style.get("outline", "#ffffff")))
    gpkg.unlink(missing_ok=True)
    run(["gdal_translate", "-of", "PNG", str(canvas), str(out_png)])
    canvas.unlink(missing_ok=True)
    Path(str(out_png) + ".aux.xml").unlink(missing_ok=True)


def make_thumbnail_raster(tif: Path, out_png: Path, bbox4326: list[float], thumb: dict) -> None:
    b, merc, w, h = _thumb_grid(bbox4326, thumb["size"], thumb["pad_raster"])
    canvas = out_png.with_suffix(".canvas.tif")
    _make_canvas(canvas, thumb, merc, w, h)
    # warp the raster onto the basemap canvas, treating 0 as transparent nodata
    run(["gdalwarp", "-q", "-r", "bilinear", "-srcnodata", "0", "-dstnodata", "0", str(tif), str(canvas)])
    run(["gdal_translate", "-of", "PNG", str(canvas), str(out_png)])
    canvas.unlink(missing_ok=True)
    Path(str(out_png) + ".aux.xml").unlink(missing_ok=True)


def build_thumb_ctx(manifest: dict, cache: Path) -> dict:
    """Read the manifest thumbnails block and prepare the shared tile basemap
    descriptor once. Everything thumbnail-specific lives in the manifest, not here.
    The basemap is an XYZ tile template (`{z}/{x}/{y}`), CARTO light by default."""
    t = manifest.get("thumbnails", {}) or {}
    basemap = None
    attribution = None
    bm = t.get("basemap")
    if bm:
        url = bm["url"] if isinstance(bm, dict) else bm
        attribution = bm.get("attribution") if isinstance(bm, dict) else None
        basemap = _tile_basemap_xml(url, cache)
    return {
        "size": int(t.get("size", 768)),
        "pad_vector": float(t.get("pad_vector", 0.06)),
        "pad_raster": float(t.get("pad_raster", 0.4)),
        "ocean": _hex_rgb(t.get("ocean_color", "#eef3f8")),
        "basemap": basemap,
        "attribution": attribution,
    }


def _thumb_desc(thumb: dict) -> str:
    if thumb.get("attribution"):
        return f"Preview thumbnail over a light basemap. {thumb['attribution']}."
    return "Preview thumbnail"
