"""The raster-scenes path, one raster cut into a grid of scenes.

core.md asks a collection of many rasters to model each scene as an Item with
its COG as an item asset. formats.md then asks that collection for an item
mirror at `items.parquet` (PORTO-FMT-040 to 043) and for a valid-data footprint
as each item geometry (PORTO-FMT-074). This module builds them from one source
raster and the manifest `grid`.

It does not build the overview COG that PORTO-FMT-067 recommends. The rashid
range pinned in build.py reports PTL-VIZ-002 for a `visual` asset that has no
style, and an overview COG has none.
"""
from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from common import filesize, multihash
from config import FILE_EXT, MEDIA, PROJ_EXT, STAC_VERSION
from convert import bands_from_cog, proj_code, to_cog

# PORTO-FMT-043 applies the GeoParquet row-group limit to an item mirror.
MAX_ROW_GROUP_ROWS = 150_000
MIRROR_NAME = "items.parquet"
MIRROR_KEY = "geoparquet-items"


def grid_windows(width: int, height: int, columns: int, rows: int) -> list[tuple[int, int, Any]]:
    """The (row, column, window) cells of a `columns` by `rows` grid over a
    raster. The cells cover every pixel exactly once. The last column and the
    last row take the remainder when the size does not divide evenly."""
    from rasterio.windows import Window

    if columns < 1 or rows < 1 or columns > width or rows > height:
        raise ValueError(f"grid {columns}x{rows} does not fit a {width}x{height} raster")
    xs = [round(i * width / columns) for i in range(columns + 1)]
    ys = [round(j * height / rows) for j in range(rows + 1)]
    return [(r, c, Window(xs[c], ys[r], xs[c + 1] - xs[c], ys[r + 1] - ys[r]))
            for r in range(rows) for c in range(columns)]


def _hull(points: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Convex hull by Andrew's monotone chain, counter-clockwise, not closed."""
    pts = sorted(set(points))
    if len(pts) < 3:
        return pts

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: list[tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def valid_footprint(tif: Path) -> dict | None:
    """The valid-data footprint of a raster as a WGS84 GeoJSON Polygon, or None
    when the raster has no valid pixel.

    The footprint is the convex hull of the valid pixels. That is exact for a
    scene whose valid area is convex, such as a rotated satellite frame cut by
    a rectangular grid cell. Interior nodata does not make a hole."""
    import numpy as np
    import rasterio
    from rasterio.warp import transform

    with rasterio.open(tif) as ds:
        mask = ds.dataset_mask() > 0
        if not mask.any():
            return None
        corners: list[tuple[float, float]] = []
        for row in np.flatnonzero(mask.any(axis=1)):
            cols = np.flatnonzero(mask[row])
            for col in (int(cols[0]), int(cols[-1]) + 1):
                for r in (int(row), int(row) + 1):
                    corners.append(ds.transform * (col, r))
        ring = _hull(corners)
        lons, lats = transform(ds.crs, "EPSG:4326", [p[0] for p in ring], [p[1] for p in ring])
    coords = [[round(x, 6), round(y, 6)] for x, y in zip(lons, lats)]
    coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


def _bbox(geometry: dict) -> list[float]:
    xs = [p[0] for p in geometry["coordinates"][0]]
    ys = [p[1] for p in geometry["coordinates"][0]]
    return [min(xs), min(ys), max(xs), max(ys)]


def write_scene_cog(src_tif: Path, window, out_tif: Path) -> None:
    """Cut one window out of the source raster and write it as a COG in the
    source CRS, with the source nodata value and embedded band statistics."""
    import rasterio

    with rasterio.open(src_tif) as src:
        meta = src.profile.copy()
        meta.update(driver="GTiff", width=int(window.width), height=int(window.height),
                    transform=src.window_transform(window))
        data = src.read(window=window)
    with tempfile.TemporaryDirectory() as tmp:
        staged = Path(tmp) / "scene.tif"
        with rasterio.open(staged, "w", **meta) as dst:
            dst.write(data)
        to_cog(staged, out_tif, None)


def build_items(src_tif: Path, coll_dir: Path, cid: str, item_title: str, depth: int,
                grid: dict, interval: list[str]) -> list[dict]:
    """Cut the source into the manifest grid and write one Item per scene, each
    with its COG beside it. Returns the Items in grid order.

    A grid cell with no valid pixel gets no Item, because it has no footprint.
    `interval` is the [start, end] that bounds every scene. The Items carry it
    as `start_datetime` and `end_datetime` with a null `datetime`.

    `item_title` is the manifest template for the Item title, with `{row}` and
    `{column}` placeholders. The Item id ends in `-r<row>c<column>`, and
    translations.py reads the row and the column back from that suffix."""
    import rasterio

    stem = cid.split("/")[-1]
    with rasterio.open(src_tif) as src:
        cells = grid_windows(src.width, src.height, grid["columns"], grid["rows"])
    items = []
    for row, col, window in cells:
        iid = f"{stem}-r{row + 1}c{col + 1}"
        item_dir = coll_dir / iid
        cog = item_dir / f"{iid}.tif"
        write_scene_cog(src_tif, window, cog)
        geometry = valid_footprint(cog)
        if geometry is None:
            cog.unlink()
            item_dir.rmdir()
            continue
        code = proj_code(cog)
        title = item_title.format(row=row + 1, column=col + 1)
        item = {
            "type": "Feature",
            "stac_version": STAC_VERSION,
            "stac_extensions": [FILE_EXT, PROJ_EXT],
            "id": iid,
            "collection": cid,
            "geometry": geometry,
            "bbox": _bbox(geometry),
            "properties": {
                "title": title,
                "datetime": None,
                "start_datetime": interval[0],
                "end_datetime": interval[1],
            },
            "assets": {
                "data": {
                    "href": f"./{cog.name}",
                    "type": MEDIA["cog"],
                    "title": f"{title} (COG)",
                    "roles": ["data"],
                    "bands": bands_from_cog(cog),
                    "proj:code": code,
                    "file:size": filesize(cog),
                    "file:checksum": multihash(cog),
                },
            },
            "links": [
                {"rel": "root", "href": "../" * (depth + 1) + "catalog.json",
                 "type": "application/json"},
                {"rel": "parent", "href": "../collection.json", "type": "application/json"},
                {"rel": "collection", "href": "../collection.json",
                 "type": "application/json"},
            ],
        }
        (item_dir / f"{iid}.json").write_text(
            json.dumps(item, ensure_ascii=False, indent=2) + "\n")
        items.append(item)
    if len(items) < 2:
        raise ValueError(f"{cid} grid gives {len(items)} scenes with valid pixels, "
                         "a raster-scenes collection needs two or more")
    return items


def hilbert_key(bbox: list[float], extent: list[float], order: int = 16) -> int:
    """The Hilbert curve index of a bbox center, on a 2^order grid over
    `extent`. Rows sorted by this key keep nearby items together."""
    n = 1 << order
    width = (extent[2] - extent[0]) or 1.0
    height = (extent[3] - extent[1]) or 1.0
    x = min(n - 1, max(0, int(((bbox[0] + bbox[2]) / 2 - extent[0]) / width * n)))
    y = min(n - 1, max(0, int(((bbox[1] + bbox[3]) / 2 - extent[1]) / height * n)))
    d = 0
    s = n >> 1
    while s > 0:
        rx = 1 if x & s else 0
        ry = 1 if y & s else 0
        d += s * s * ((3 * rx) ^ ry)
        if ry == 0:
            if rx == 1:
                x, y = n - 1 - x, n - 1 - y
            x, y = y, x
        s >>= 1
    return d


def items_extent(items: list[dict]) -> list[float]:
    boxes = [i["bbox"] for i in items]
    return [min(b[0] for b in boxes), min(b[1] for b in boxes),
            max(b[2] for b in boxes), max(b[3] for b in boxes)]


def hilbert_sorted(items: list[dict]) -> list[dict]:
    """The items in Hilbert curve order over their own extent, with the id as
    the tie-break so the order does not depend on the input order."""
    extent = items_extent(items)
    return sorted(items, key=lambda i: (hilbert_key(i["bbox"], extent), i["id"]))


def write_items_parquet(items: list[dict], out: Path, row_group_size: int = 1024) -> int:
    """Write the stac-geoparquet item mirror, one row per Item, in Hilbert
    order. Returns the row count.

    PORTO-FMT-043 applies the GeoParquet rules to this file. The
    stac-geoparquet writer does not sort rows, so this function sorts them
    before the write. The write goes through `stac_geoparquet.arrow.to_parquet`
    and not `pyarrow.parquet.write_table`, because only the first one writes
    the `geo` metadata key. Without that key a validator reads the file as
    plain Parquet and skips each GeoParquet rule."""
    if row_group_size > MAX_ROW_GROUP_ROWS:
        raise ValueError(f"row_group_size {row_group_size} is more than the "
                         f"PORTO-FMT-043 limit of {MAX_ROW_GROUP_ROWS}")
    # A heavy dependency, so the import stays in the one function that needs it.
    import stac_geoparquet.arrow

    # The import sets the root logger to INFO, which prints a line per batch.
    logging.getLogger("stac_geoparquet").setLevel(logging.WARNING)
    table = stac_geoparquet.arrow.parse_stac_items_to_arrow(hilbert_sorted(items)).read_all()
    out.parent.mkdir(parents=True, exist_ok=True)
    stac_geoparquet.arrow.to_parquet(
        table.to_reader(max_chunksize=row_group_size), out, compression="zstd")
    return table.num_rows


def read_items(coll_dir: Path, coll: dict) -> list[dict]:
    """The Items of a built collection, read through its `item` links."""
    return [json.loads((coll_dir / l["href"]).read_text())
            for l in coll["links"] if l["rel"] == "item"]
