"""XYZ basemap tiles for thumbnails.

Fetches Web Mercator XYZ raster tiles over HTTP, caches them under
`.cache/tiles`, and mosaics the covering tiles into a numpy RGB array cropped
and resampled to a framed Mercator extent. Replaces the GDAL WMS descriptor the
thumbnail path used to hand gdalwarp.
"""
from __future__ import annotations

import math
from pathlib import Path
from urllib.request import Request, urlopen

import numpy as np
from PIL import Image

from config import USER_AGENT

_ORIGIN = math.pi * 6378137.0  # 20037508.342789244, half the Mercator world
_WORLD = 2 * _ORIGIN
_TILE = 256


def _tile_zoom(merc: list[float], w: int, max_zoom: int = 19) -> int:
    """Pick the XYZ zoom whose pixel width across the framed Mercator extent is
    closest to the output width `w`, so basemap detail matches the thumbnail."""
    span = abs(merc[2] - merc[0]) or 1.0
    z = round(math.log2(max(w, 1) * _WORLD / (span * _TILE)))
    return max(0, min(max_zoom, int(z)))


def _merc_to_tile(x: float, y: float, z: int) -> tuple[float, float]:
    """Fractional tile coordinates from the top-left origin for a Mercator point."""
    n = 2 ** z
    fx = (x + _ORIGIN) / _WORLD
    fy = (_ORIGIN - y) / _WORLD
    return fx * n, fy * n


def _fetch_tile(url: str, z: int, x: int, y: int, cache: Path) -> Path:
    """Fetch one XYZ tile to `.cache/tiles/{z}/{x}/{y}.png`, cached. Raises on a
    fetch failure with the tile URL, no silent holes in the mosaic."""
    p = cache / "tiles" / str(z) / str(x) / f"{y}.png"
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    tile_url = url.format(z=z, x=x, y=y)
    try:
        req = Request(tile_url, headers={"User-Agent": USER_AGENT})
        with urlopen(req, timeout=30) as r:
            data = r.read()
    except Exception as e:
        raise RuntimeError(f"basemap tile fetch failed: {tile_url}") from e
    p.write_bytes(data)
    return p


def fetch_basemap(url: str, merc: list[float], w: int, h: int, cache: Path) -> np.ndarray:
    """Fetch and mosaic the XYZ basemap for the framed Mercator extent into an
    `(h, w, 3)` uint8 RGB array. `merc` is `[x0, y0, x1, y1]` in EPSG:3857
    meters."""
    x0, y0, x1, y1 = merc
    z = _tile_zoom(merc, w)
    n = 2 ** z
    # top-left corner is (minx, maxy), bottom-right is (maxx, miny)
    ftx0, fty0 = _merc_to_tile(x0, y1, z)
    ftx1, fty1 = _merc_to_tile(x1, y0, z)
    xa, xb = math.floor(ftx0), math.ceil(ftx1)
    ya, yb = math.floor(fty0), math.ceil(fty1)
    mosaic = Image.new("RGB", ((xb - xa) * _TILE, (yb - ya) * _TILE), (238, 243, 248))
    for tx in range(xa, xb):
        for ty in range(ya, yb):
            cx, cy = max(0, min(n - 1, tx)), max(0, min(n - 1, ty))
            tile = Image.open(_fetch_tile(url, z, cx, cy, cache)).convert("RGB")
            mosaic.paste(tile, ((tx - xa) * _TILE, (ty - ya) * _TILE))
    box = (round((ftx0 - xa) * _TILE), round((fty0 - ya) * _TILE),
           round((ftx1 - xa) * _TILE), round((fty1 - ya) * _TILE))
    framed = mosaic.crop(box).resize((w, h), Image.BILINEAR)
    # np.array copies (asarray would return a read-only view over the PIL
    # buffer), so callers can paint features onto the canvas in place.
    return np.array(framed, dtype=np.uint8)
