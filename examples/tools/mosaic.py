"""The raster-mosaic path, a Portolan mirror of COGs hosted elsewhere.

A mosaic collection describes many scenes it does not host. core.md requires each
scene to be an item carrying its COG as an item-level asset, so this module emits
items rather than a collection-level data asset. The COG bytes stay upstream, so
`file:size` comes from a HEAD and `file:checksum` is omitted rather than invented,
see NAIP-MIRROR-FOLLOWUP.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from fetch import fetch


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
