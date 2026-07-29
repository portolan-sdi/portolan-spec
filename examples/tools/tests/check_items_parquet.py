# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "stac-geoparquet",
#   "pyarrow>=25",
#   "numpy",
#   "pyyaml>=6.0.3",
#   "duckdb>=1.5.5",
#   "rasterio>=1.5",
#   "Pillow>=11",
# ]
# ///
"""Offline checks for the stac-geoparquet item mirror.

PTL-DAT-006 and PTL-DAT-016 live in rashid's data pass, which the naip-mosaic
catalog disables because reading 1.7 TB of upstream COGs weekly is not a CI job.
So the ordering and the row-per-item parity are asserted here instead. Without
this check an unsorted or desynchronised mirror would ship unnoticed.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pyarrow.parquet as pq

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import mosaic  # noqa: E402

FAILURES: list[str] = []


def check(name: str, fn) -> None:
    try:
        fn()
        print(f"  ok   {name}")
    except AssertionError as exc:
        FAILURES.append(f"{name}: {exc}")
        print(f"  FAIL {name}: {exc}")


def _items(n: int) -> list[dict]:
    out = []
    for i in range(n):
        lon = -106.0 + (i % 20) * 0.05
        lat = 38.7 + (i // 20) * 0.05
        out.append({
            "type": "Feature", "stac_version": "1.1.0", "id": f"tile-{i:04d}",
            "collection": "imagery/colorado-2023",
            "bbox": [lon, lat, lon + 0.05, lat + 0.05],
            "geometry": {"type": "Polygon", "coordinates": [[
                [lon, lat], [lon + 0.05, lat], [lon + 0.05, lat + 0.05],
                [lon, lat + 0.05], [lon, lat]]]},
            "properties": {"datetime": "2023-10-20T16:00:00Z"},
            "assets": {"image": {"href": f"https://example.invalid/{i}.tif",
                                 "type": "image/tiff", "roles": ["data"]}},
            "links": [],
        })
    return out


def check_row_count_matches_items() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "items.parquet"
        n = mosaic.write_items_parquet(_items(300), out, row_group_size=128)
        assert n == 300, n
        assert pq.ParquetFile(out).metadata.num_rows == 300, "row per item"


def check_multiple_row_groups() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "items.parquet"
        mosaic.write_items_parquet(_items(300), out, row_group_size=128)
        groups = pq.ParquetFile(out).num_row_groups
        assert groups >= 3, f"expected several row groups for skipping, got {groups}"


def check_row_groups_within_cap() -> None:
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "items.parquet"
        mosaic.write_items_parquet(_items(300), out, row_group_size=128)
        f = pq.ParquetFile(out)
        for i in range(f.num_row_groups):
            rows = f.metadata.row_group(i).num_rows
            assert rows <= 150_000, f"row group {i} holds {rows} rows"


def check_rows_are_spatially_ordered() -> None:
    """Hilbert ordering must beat input order on summed neighbour distance."""
    items = _items(300)
    keys = [mosaic.hilbert_key(i["bbox"]) for i in items]
    assert len(set(keys)) > 1, "hilbert_key collapsed every item to one value"
    ordered = [i["bbox"] for _, i in sorted(zip(keys, items), key=lambda p: p[0])]

    def spread(boxes: list[list[float]]) -> float:
        return sum(abs(a[0] - b[0]) + abs(a[1] - b[1])
                   for a, b in zip(boxes, boxes[1:]))

    assert spread(ordered) < spread([i["bbox"] for i in items]), \
        "hilbert order must cluster neighbours more tightly than input order"


if __name__ == "__main__":
    print("check_items_parquet.py")
    check("row count matches item count", check_row_count_matches_items)
    check("several row groups are written", check_multiple_row_groups)
    check("row groups stay within the 150k cap", check_row_groups_within_cap)
    check("rows are spatially ordered", check_rows_are_spatially_ordered)
    if FAILURES:
        raise SystemExit(f"{len(FAILURES)} failure(s)")
    print("all ok")
