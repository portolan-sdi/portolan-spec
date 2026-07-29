"""The raster-mosaic path, a Portolan mirror of COGs hosted elsewhere.

A mosaic collection describes many scenes it does not host. core.md requires each
scene to be an item carrying its COG as an item-level asset, so this module emits
items rather than a collection-level data asset. The COG bytes stay upstream, so
`file:size` comes from a HEAD and `file:checksum` is omitted rather than invented,
see NAIP-MIRROR-FOLLOWUP.md.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import numpy as np
import rasterio
from rasterio.enums import Resampling

from config import USER_AGENT
from fetch import fetch

# /vsicurl issues a directory listing per open unless told not to, which triples
# the request count against a blob store that has no directories anyway.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")


def fetch_stac_items(url: str, cache: Path, stable: bool = False) -> list[dict]:
    """Every item from a STAC search response, refusing a truncated result.

    The manifest sizes `limit` so one request covers the query. A `next` link
    means the upstream grew past that, which would silently publish a partial
    mosaic, so it fails the build instead.
    """
    local = fetch(url, cache, stable=stable)
    doc = json.loads(local.read_text(encoding="utf-8"))
    features = doc.get("features") or []
    if not features:
        raise SystemExit(f"{url} returned no features")
    if any(link.get("rel") == "next" for link in doc.get("links") or []):
        raise SystemExit(
            f"{url} has an unconsumed next page, {len(features)} features read. "
            "Raise the manifest limit so one request covers the query.")
    print(f"  {len(features)} items from the STAC search", file=sys.stderr)
    return features


def remote_size(href: str) -> int:
    """`Content-Length` for an asset this catalog does not host.

    core.md requires `file:size` on every asset and rashid verifies it against
    the bytes, so this is read fresh at build time rather than cached.
    """
    req = urllib.request.Request(href, method="HEAD",
                                 headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            length = r.headers.get("Content-Length")
    except (urllib.error.HTTPError, urllib.error.URLError,
            TimeoutError, OSError) as exc:
        raise SystemExit(f"HEAD {href} failed, {exc}") from exc
    if not length:
        raise SystemExit(f"{href} returned no Content-Length, so file:size is unknowable")
    return int(length)


def read_overview(href: str) -> tuple[list[dict], np.ndarray]:
    """STAC 1.1 `bands` and the coarsest overview for one COG.

    One range-read pass serves both the statistics and the thumbnail mosaic. The
    upstream COGs carry no embedded STATISTICS_* tags, so these are computed here.
    They are derived from an overview rather than full resolution and are flagged
    `approximate`, which is what the incubating stats encoding asks for. They do
    not satisfy PORTO-FMT-026, which requires statistics embedded in the file, and
    that failure is baselined rather than papered over.
    """
    path = href if href.startswith("/vsicurl/") or Path(href).exists() else f"/vsicurl/{href}"
    with rasterio.open(path) as d:
        levels = d.overviews(1)
        factor = levels[-1] if levels else 1
        shape = (d.count, max(1, d.height // factor), max(1, d.width // factor))
        arr = d.read(out_shape=shape, resampling=Resampling.average)
        dtypes = list(d.dtypes)
    bands: list[dict] = []
    for i in range(arr.shape[0]):
        plane = arr[i].astype("float64")
        bands.append({
            "data_type": dtypes[i],
            "statistics": {
                "minimum": float(plane.min()),
                "maximum": float(plane.max()),
                "mean": round(float(plane.mean()), 6),
                "stddev": round(float(plane.std()), 6),
                "approximate": True,
            },
        })
    return bands, arr
