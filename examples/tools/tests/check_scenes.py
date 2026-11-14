# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "duckdb>=1.5.5",
#   "rasterio>=1.5",
#   "rio-cogeo>=5.3",
#   "numpy",
#   "pyarrow>=25",
#   "pyyaml>=6.0.3",
#   "stac-geoparquet>=0.8.3,<0.9",
# ]
# ///
"""Standalone check for scenes.py and the committed raster-scenes collections.

rashid cannot judge the row order of an item mirror that has fewer than 200
rows, so a small mirror passes PORTO-FMT-043 without a measurement. This check
measures the order itself. It also covers the rules that a wrong writer breaks
with no error from a validator.

- The grid covers each source pixel one time.
- An Item geometry is the valid-data footprint, not the grid cell.
- The item mirror has the `geo` key, one row for each Item, and Hilbert order.
- Each committed raster-scenes collection has a mirror that matches its Items.

Run: uv run examples/tools/tests/check_scenes.py
"""
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import rasterio
import yaml
from rasterio.transform import from_origin

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from scenes import (  # noqa: E402
    MIRROR_KEY, MIRROR_NAME, build_items, grid_windows, hilbert_sorted,
    read_items, valid_footprint, write_items_parquet,
)

EXAMPLES = HERE.parent.parent
INTERVAL = ["2000-01-01T00:00:00Z", "2000-12-31T23:59:59Z"]


def _source(path: Path, size: int = 64) -> None:
    """A 3-band UTM raster whose valid pixels are the lower-left triangle."""
    rows, cols = np.mgrid[0:size, 0:size]
    valid = cols <= rows
    data = np.where(valid, 100, 0).astype("uint8")
    with rasterio.open(path, "w", driver="GTiff", height=size, width=size, count=3,
                       dtype="uint8", crs="EPSG:32618", nodata=0,
                       transform=from_origin(200000, 2800000, 300, 300)) as dst:
        for band in (1, 2, 3):
            dst.write(data, band)


def check_grid() -> None:
    seen = np.zeros((718, 791), dtype=int)
    cells = grid_windows(791, 718, 4, 4)
    assert len(cells) == 16
    for _, _, w in cells:
        seen[w.row_off:w.row_off + w.height, w.col_off:w.col_off + w.width] += 1
    assert (seen == 1).all(), "the grid must cover each pixel one time"
    try:
        grid_windows(4, 4, 5, 1)
    except ValueError:
        pass
    else:
        raise AssertionError("a grid larger than the raster must fail")


def _row_jumps(ids: list[str], centers: dict[str, tuple[float, float]]) -> float:
    return sum(abs(centers[a][0] - centers[b][0]) + abs(centers[a][1] - centers[b][1])
               for a, b in zip(ids, ids[1:]))


def check_build(tmp: Path) -> None:
    src = tmp / "source.tif"
    _source(src)
    coll_dir = tmp / "raster" / "scenes"
    items = build_items(src, coll_dir, "raster/scenes", "Scene {row}-{column}", 2,
                        {"columns": 4, "rows": 4}, INTERVAL)
    # The 6 cells above the diagonal have no valid pixel, so they get no Item.
    assert len(items) == 10, len(items)
    ids = [i["id"] for i in items]
    assert "scenes-r1c4" not in ids and "scenes-r4c1" in ids
    for item in items:
        cog = coll_dir / item["id"] / f"{item['id']}.tif"
        assert cog.exists() and (coll_dir / item["id"] / f"{item['id']}.json").exists()
        with rasterio.open(cog) as ds:
            assert ds.nodata == 0, "PORTO-FMT-073, each scene declares nodata"
        assert item["properties"]["datetime"] is None
        assert item["properties"]["start_datetime"] == INTERVAL[0]
        assert item["assets"]["data"]["proj:code"] == "EPSG:32618"
        assert item["links"][0]["href"] == "../../../catalog.json"
    # A cell on the diagonal is half valid, so its footprint is a triangle.
    diagonal = next(i for i in items if i["id"] == "scenes-r1c1")
    ring = diagonal["geometry"]["coordinates"][0]
    assert ring[0] == ring[-1]
    full = next(i for i in items if i["id"] == "scenes-r4c1")
    assert len(full["geometry"]["coordinates"][0]) == 5, "a full cell is a rectangle"

    def area(i):
        b = i["bbox"]
        r = i["geometry"]["coordinates"][0]
        shoelace = abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(r, r[1:]))) / 2
        return shoelace / ((b[2] - b[0]) * (b[3] - b[1]))

    assert area(full) > 0.95 and area(diagonal) < 0.75, (area(full), area(diagonal))
    assert valid_footprint(coll_dir / "scenes-r4c1" / "scenes-r4c1.tif") == full["geometry"]

    mirror = coll_dir / MIRROR_NAME
    assert write_items_parquet(list(reversed(items)), mirror) == 10
    pf = pq.ParquetFile(mirror)
    assert b"geo" in pf.schema_arrow.metadata, "the mirror must be GeoParquet"
    rows = pf.read().column("id").to_pylist()
    assert rows == [i["id"] for i in hilbert_sorted(items)]
    assert sorted(rows) == sorted(ids)
    # The Hilbert order must keep neighbors together better than the id order.
    centers = {i["id"]: ((i["bbox"][0] + i["bbox"][2]) / 2, (i["bbox"][1] + i["bbox"][3]) / 2)
               for i in items}
    assert _row_jumps(rows, centers) < _row_jumps(sorted(ids), centers)
    try:
        write_items_parquet(items, mirror, row_group_size=150_001)
    except ValueError:
        pass
    else:
        raise AssertionError("a row group over the PORTO-FMT-043 limit must fail")


def check_committed() -> int:
    """Each committed raster-scenes collection has a mirror equal to its Items."""
    count = 0
    for manifest in sorted((EXAMPLES / "manifests").glob("*.yaml")):
        for spec in yaml.safe_load(manifest.read_text())["collections"]:
            if spec["kind"] != "raster-scenes":
                continue
            count += 1
            coll_dir = EXAMPLES / "catalog" / manifest.stem / spec["id"]
            coll = json.loads((coll_dir / "collection.json").read_text())
            assert "data" not in coll["assets"], "scene COGs are item assets"
            mirror = coll["assets"][MIRROR_KEY]
            assert mirror["roles"] == ["collection-mirror"]
            assert mirror["type"] == "application/vnd.apache.parquet"
            assert mirror["href"] == f"./{MIRROR_NAME}"
            items = read_items(coll_dir, coll)
            want = spec["grid"]["columns"] * spec["grid"]["rows"]
            assert 2 <= len(items) <= want, (spec["id"], len(items))
            table = pq.ParquetFile(coll_dir / MIRROR_NAME).read()
            assert table.column("id").to_pylist() == [i["id"] for i in hilbert_sorted(items)], \
                f"{spec['id']} mirror rows are not the Items in Hilbert order"
            by_id = {i["id"]: i for i in items}
            for row in table.select(["id", "bbox", "assets"]).to_pylist():
                item = by_id[row["id"]]
                assert [row["bbox"][k] for k in ("xmin", "ymin", "xmax", "ymax")] == item["bbox"]
                assert row["assets"]["data"]["file:checksum"] == \
                    item["assets"]["data"]["file:checksum"]
    return count


def main() -> int:
    check_grid()
    with tempfile.TemporaryDirectory() as tmp:
        check_build(Path(tmp))
    n = check_committed()
    print(f"OK, grid, footprints, mirror order, {n} committed raster-scenes collection(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
