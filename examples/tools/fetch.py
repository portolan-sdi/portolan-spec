"""Download sources into the cache and prepare them for reading.

Fetches each upstream file once into a content-addressed cache and unpacks
zipped shapefiles so the converters can read a single-file OGR source.
"""
from __future__ import annotations

import hashlib
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path


# --------------------------------------------------------------------------- io
def fetch(url: str, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    tail = url.split("/")[-1].split("?")[0]
    suffix = "".join(c for c in tail if c.isalnum() or c in "._-")[-48:] or "download"
    dest = cache / f"{key}-{suffix}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    print(f"  fetch {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "portolan-reference/0.1"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=180) as r, tmp.open("wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    tmp.rename(dest)
    return dest


# ------------------------------------------------------------------ conversions
def _is_zip(local: Path, spec_source: dict) -> bool:
    if spec_source.get("media_type") == "application/zip" or local.name.endswith(".zip"):
        return True
    with local.open("rb") as f:
        return f.read(2) == b"PK"


def _prepare_ogr_source(local: Path, spec_source: dict, extract_dir: Path) -> tuple[str, str | None]:
    """Return (gdal_path, layer_positional). Zip sources are extracted so the
    .shp (with its .prj/.cpg siblings) is read directly, independent of the
    cached filename's extension (GDAL /vsizip keys off a .zip suffix)."""
    layer = spec_source.get("layer")
    if _is_zip(local, spec_source):
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)
        with zipfile.ZipFile(local) as z:
            z.extractall(extract_dir)
        shps = sorted(extract_dir.rglob("*.shp"))
        assert shps, f"no .shp found inside {local}"
        if layer:
            match = [s for s in shps if s.stem == layer]
            shp = match[0] if match else shps[0]
        else:
            shp = shps[0]
        return str(shp), None
    # gpkg / geojson / other single-file OGR source
    return str(local), layer
