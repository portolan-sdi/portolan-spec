"""The raster-mosaic path, a Portolan mirror of COGs hosted elsewhere.

A mosaic collection describes many scenes it does not host. core.md requires each
scene to be an item carrying its COG as an item-level asset, so this module emits
items rather than a collection-level data asset. The COG bytes stay upstream, so
`file:size` comes from a HEAD and `file:checksum` is omitted rather than invented,
see NAIP-MIRROR-FOLLOWUP.md.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

import numpy as np
import rasterio
import rasterio.errors
from PIL import Image
from rasterio.enums import Resampling

from config import FILE_EXT, MEDIA, PROJ_EXT, STAC_VERSION, USER_AGENT
from fetch import fetch
from stacio import link, remote_asset
from thumbnails import _make_canvas_arr, _thumb_grid, _to_merc

# /vsicurl issues a directory listing per open unless told not to, which triples
# the request count against a blob store that has no directories anyway.
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")

# GDAL has no default timeout, so one unresponsive object would stall a whole
# build. These bound a single read the way remote_size bounds its HEAD.
os.environ.setdefault("GDAL_HTTP_CONNECTTIMEOUT", "30")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")


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
    if any(entry.get("rel") == "next" for entry in doc.get("links") or []):
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
    that failure is baselined rather than papered over. A missing overview is an
    error, not absorbed, because reading full resolution would pull gigabytes over
    a slow network. The read itself is time-bounded by the module's GDAL HTTP
    timeout settings, so one unresponsive object fails rather than stalling.
    """
    path = href if href.startswith("/vsicurl/") or Path(href).exists() else f"/vsicurl/{href}"
    try:
        with rasterio.open(path) as d:
            levels = d.overviews(1)
            if not levels:
                raise SystemExit(
                    f"{href} reports no overviews, so a read would pull the scene "
                    "at full resolution")
            factor = levels[-1]
            shape = (d.count, max(1, d.height // factor), max(1, d.width // factor))
            arr = d.read(out_shape=shape, resampling=Resampling.average)
            dtypes = list(d.dtypes)
    except rasterio.errors.RasterioIOError as exc:
        raise SystemExit(f"cannot open {href}, {exc}") from exc
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


# Properties worth carrying from upstream. Everything else on the MPC item is
# either an API artifact or restated by the asset.
_KEEP = ("datetime", "start_datetime", "end_datetime", "gsd",
         "proj:shape", "proj:transform", "proj:bbox", "proj:centroid")


def probe_remote(href: str) -> tuple[int, list[dict], np.ndarray]:
    """Size, statistics and overview pixels for one upstream COG."""
    size = remote_size(href)
    bands, arr = read_overview(href)
    return size, bands, arr


def _proj_code(props: dict) -> str | None:
    if props.get("proj:code"):
        return str(props["proj:code"])
    if props.get("proj:epsg"):
        return f"EPSG:{props['proj:epsg']}"
    return None


def _image_href(feature: dict) -> str:
    """The upstream COG href for one feature, naming the feature when it is missing.

    924 scenes make a bare KeyError useless for finding which one was malformed,
    so this names the feature id the way every other failure in this module does.
    """
    image = (feature.get("assets") or {}).get("image") or {}
    href = image.get("href")
    if not href:
        raise SystemExit(f"{feature.get('id')} has no image asset href")
    return href


def build_items(features: list[dict], coll_dir: Path, cid: str, title: str,
                probe: Callable[[str], tuple[int, list[dict], np.ndarray]],
                ) -> tuple[list[dict], list[dict], list[float],
                           list[tuple[list[float], np.ndarray]]]:
    """Write one item.json per scene and return them with their links and bbox.

    core.md requires a multi-scene raster collection to model each scene as an
    item with the COG as an item-level asset, and forbids listing scene COGs as
    collection-level assets.
    """
    depth = len(cid.split("/"))

    # Both checks below read only what the search response already carries, so
    # they run before a single probe goes out. A malformed scene anywhere in
    # the batch fails here rather than after 924 network round trips.
    hrefs: list[str] = []
    for feature in features:
        props = feature.get("properties") or {}
        if not props.get("datetime"):
            raise SystemExit(
                f"{feature.get('id')} has no datetime, so it cannot be a conforming item")
        hrefs.append(_image_href(feature))

    with ThreadPoolExecutor(max_workers=8) as pool:
        probed = list(pool.map(probe, hrefs))

    items: list[dict] = []
    links: list[dict] = []
    tiles: list[tuple[list[float], np.ndarray]] = []
    for feature, href, (size, bands, arr) in zip(features, hrefs, probed, strict=True):
        iid = feature["id"]
        props = feature.get("properties") or {}
        out = {k: v for k, v in props.items() if k in _KEEP}
        code = _proj_code(props)
        if code:
            out["proj:code"] = code
        item = {
            "type": "Feature",
            "stac_version": STAC_VERSION,
            "stac_extensions": [FILE_EXT, PROJ_EXT],
            "id": iid,
            "collection": cid,
            "geometry": feature["geometry"],
            "bbox": feature["bbox"],
            "properties": out,
            "assets": {"image": remote_asset(
                href, MEDIA["cog"], ["data"],
                f"{title} scene {iid}", size,
                {"bands": bands} | ({"proj:code": code} if code else {}))},
            "links": [
                link("root", "../" * (depth + 1) + "catalog.json", "application/json"),
                link("parent", "../collection.json", "application/json"),
                link("collection", "../collection.json", "application/json"),
            ],
        }
        item_dir = coll_dir / iid
        item_dir.mkdir(parents=True, exist_ok=True)
        (item_dir / "item.json").write_text(json.dumps(item, indent=2) + "\n")
        items.append(item)
        links.append(link("item", f"./{iid}/item.json", "application/geo+json", iid))
        tiles.append((feature["bbox"], arr))

    bboxes = [i["bbox"] for i in items]
    bbox = [min(b[0] for b in bboxes), min(b[1] for b in bboxes),
            max(b[2] for b in bboxes), max(b[3] for b in bboxes)]
    return items, links, bbox, tiles


# PORTO-FMT-043 caps a row group at 150,000 rows, so no caller can ask for more.
MAX_ROW_GROUP_ROWS = 150_000


def hilbert_key(bbox: list[float], order: int = 16) -> int:
    """A Hilbert index for a bbox centroid, for spatially clustering rows.

    Standard xy2d Hilbert index on a 2**order grid over WGS84. Good enough
    to cluster neighbours, which is what a row-group skip needs.
    """
    side = 1 << order
    cx = (bbox[0] + bbox[2]) / 2.0
    cy = (bbox[1] + bbox[3]) / 2.0
    x = min(side - 1, max(0, int((cx + 180.0) / 360.0 * side)))
    y = min(side - 1, max(0, int((cy + 90.0) / 180.0 * side)))
    d = 0
    s = side >> 1
    while s > 0:
        rx = 1 if (x & s) > 0 else 0
        ry = 1 if (y & s) > 0 else 0
        d += s * s * ((3 * rx) ^ ry)
        # Rotate the quadrant. The reflection folds against the full grid side,
        # not against the current level, which is what makes the curve continuous.
        if ry == 0:
            if rx == 1:
                x = side - 1 - x
                y = side - 1 - y
            x, y = y, x
        s >>= 1
    return d


def write_items_parquet(items: list[dict], out: Path,
                        row_group_size: int = 128) -> int:
    """The stac-geoparquet item mirror, spatially ordered before the write.

    PORTO-FMT-043 binds this file to the GeoParquet storage rules, spatially
    ordered rows, per-row-group spatial statistics, and row groups no larger than
    150,000 rows. The plain stac-geoparquet writer applies no sorting and sets no
    row-group size, and rashid rejects the result with PTL-DAT-006, so rows are
    Hilbert-sorted and the row-group size is set explicitly. Registered by the
    caller as a collection-level asset with the `collection-mirror` role, which
    PORTO-FMT-041 says is the whole requirement, no `rel: "items"` link needed.

    A spike measured this writer and geoparquet-io's web profile against the
    pinned rashid over a 924-item fixture. Both clear PTL-DAT-006 at 8 row
    groups. This one wins on fidelity. geoparquet-io routes the table through
    DuckDB, which widens every string to `large_string` and every list to
    `large_list`, and which restamps the `datetime` column with the builder's
    local timezone rather than UTC, so the same items produce different bytes on
    different machines. It also needs the same explicit row-group cap, because
    its byte-targeted profile writes 924 small rows as one row group. See
    NAIP-MIRROR-FOLLOWUP.md for the measurements.

    The batches carry no `geo` metadata of their own, so the write goes through
    stac-geoparquet's own `to_parquet` rather than `pyarrow.parquet.write_table`.
    A plain `write_table` drops the `geo` key, and rashid then reads the file as
    plain Parquet and skips every GeoParquet rule, which passes for the wrong
    reason. Row groups come from the batch size, since `to_parquet` writes one
    row group per batch.
    """
    if row_group_size > MAX_ROW_GROUP_ROWS:
        raise SystemExit(
            f"row_group_size {row_group_size} exceeds the PORTO-FMT-043 cap of "
            f"{MAX_ROW_GROUP_ROWS}")

    # stac-geoparquet is scoped to this function, the house pattern for a heavy
    # dependency, and load bearing because tests/check_mosaic.py resolves none.
    import stac_geoparquet

    # Importing it calls logging.basicConfig at INFO on stdout, which prints a
    # per-batch progress line into whatever the caller is writing there.
    logging.getLogger("stac_geoparquet").setLevel(logging.WARNING)

    ordered = [i for _, i in sorted(
        ((hilbert_key(i["bbox"]), i) for i in items), key=lambda p: p[0])]
    table = stac_geoparquet.arrow.parse_stac_items_to_arrow(ordered).read_all()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.unlink(missing_ok=True)
    stac_geoparquet.arrow.to_parquet(
        table.to_reader(max_chunksize=row_group_size),
        out, compression="zstd")
    return table.num_rows


def write_minimal_json(items: list[dict], out: Path) -> int:
    """A compact bbox-plus-href index for browser mosaic clients.

    Not something the spec asks for. It exists because a client-side mosaic needs
    every footprint and href in one request, which is why deck.gl-raster hand-baked
    such a file rather than calling a STAC API per load. Registered with the
    `metadata` role, and evidence for spec issue #44.
    """
    doc = {
        "type": "FeatureCollection",
        "features": [
            {"bbox": i["bbox"],
             "assets": {"image": {"href": i["assets"]["image"]["href"]}}}
            for i in items
        ],
    }
    out.write_text(json.dumps(doc, separators=(",", ":")) + "\n")
    return len(doc["features"])


def make_thumbnail_mosaic(tiles: list[tuple[list[float], np.ndarray]], out_png: Path,
                          bbox4326: list[float], thumb: dict) -> None:
    """Paste each scene's overview into one Mercator canvas.

    The pixels are the real upstream imagery, read once per scene at its coarsest
    overview, so the preview shows the mosaic rather than a footprint sketch.
    """
    _, merc, w, h = _thumb_grid(bbox4326, thumb["size"], thumb.get("pad_raster", 0.4))
    canvas = _make_canvas_arr(thumb, merc, w, h)

    span_x = merc[2] - merc[0]
    span_y = merc[3] - merc[1]
    for bbox, arr in tiles:
        x0, y0 = _to_merc(bbox[0], bbox[1])
        x1, y1 = _to_merc(bbox[2], bbox[3])
        # Mercator y grows north, raster rows grow south.
        left = int(round((min(x0, x1) - merc[0]) / span_x * w))
        right = int(round((max(x0, x1) - merc[0]) / span_x * w))
        top = int(round((merc[3] - max(y0, y1)) / span_y * h))
        bottom = int(round((merc[3] - min(y0, y1)) / span_y * h))
        tw, th = max(1, right - left), max(1, bottom - top)
        if left >= w or top >= h or right <= 0 or bottom <= 0:
            continue
        rgb = np.moveaxis(arr[:3], 0, -1) if arr.shape[0] >= 3 else \
            np.repeat(np.moveaxis(arr[:1], 0, -1), 3, axis=-1)
        patch = np.asarray(Image.fromarray(rgb.astype("uint8")).resize(
            (tw, th), Image.BILINEAR))
        sl = (slice(max(0, top), min(h, bottom)), slice(max(0, left), min(w, right)))
        ph, pw = sl[0].stop - sl[0].start, sl[1].stop - sl[1].start
        canvas[sl] = patch[:ph, :pw]

    Image.fromarray(canvas).save(out_png, optimize=True)
