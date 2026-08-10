# /// script
# requires-python = ">=3.12"
# dependencies = [
#   # Bounded, and kept level with build.py's own bound. This writer determines
#   # the published file:checksum of items.parquet, so a floor here means these
#   # checks and the build read the same writer.
#   "stac-geoparquet>=0.8.1",
#   "pyarrow>=25",
#   "numpy",
#   "pyyaml>=6.0.3",
#   "duckdb>=1.5.5",
#   "rasterio>=1.5",
#   "Pillow>=11",
# ]
# ///
"""Offline checks for the stac-geoparquet item mirror writer.

PTL-DAT-006 and PTL-DAT-016 do run against the built items.parquet now.
The naip-mosaic catalog uses rashid's --data-scope local, so every data rule is
applied to assets inside the catalog tree while its 1.86 TB of remote COGs are
treated as unfetchable. These checks are no longer the only thing standing
between us and an unsorted mirror, and the docstring said otherwise until the
scope was adopted.

They stay because they cover something the gate does not. They exercise
write_items_parquet directly over a synthetic fixture, so they fail on a writer
regression without a rebuild and without invoking rashid, which makes them a fast
inner-loop check. The gate proves the built artifact, these prove the code
that produces it.
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


def check_default_row_group_size_keeps_locality_margin() -> None:
    """The default must clear PTL-DAT-006 on locality with real margin.

    Every consecutive row-group pair in this file overlaps, so the low-overlap
    criterion fails and locality is the only thing carrying the rule. rashid
    compares the mean row-group bbox area over the file extent against a flat
    0.30, and applies the row-group criteria only at five or more groups, both
    from PORTO-FMT-006 and PORTO-FMT-044 as rewritten in spec #133.

    The limit used to be `max(0.25, 2.0 / groups)`, a group-count relaxation
    that stopped at eight groups. The old default row_group_size of 128 put the
    924-scene build on exactly eight, scoring 0.2467 against 0.250, so a few
    scenes either way flipped the gate for no change in quality. The flat limit
    removes that cliff, and this still pins the margin rather than only the pass
    so a writer regression cannot creep up on it.
    """
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "items.parquet"
        mosaic.write_items_parquet(_items(924), out)
        meta = pq.ParquetFile(out).metadata
        names = [meta.schema.column(i).path for i in range(len(meta.schema))]
        ix = {n: i for i, n in enumerate(names) if n.startswith("bbox.")}
        assert ix, "the covering bbox column is what carries row-group statistics"
        boxes = []
        for g in range(meta.num_row_groups):
            rg = meta.row_group(g)
            st = {n: rg.column(i).statistics for n, i in ix.items()}
            boxes.append((st["bbox.xmin"].min, st["bbox.ymin"].min,
                          st["bbox.xmax"].max, st["bbox.ymax"].max))

        def area(b) -> float:
            return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])

        extent = (min(b[0] for b in boxes), min(b[1] for b in boxes),
                  max(b[2] for b in boxes), max(b[3] for b in boxes))
        ratio = sum(area(b) for b in boxes) / len(boxes) / area(extent)
        assert len(boxes) >= 5, (
            f"{len(boxes)} row groups, under the five where PORTO-FMT-044 lets "
            "rashid judge the row-group criteria at all, so this asserts nothing")
        limit = 0.30
        assert ratio < limit, f"locality {ratio:.4f} is over the {limit:.3f} limit"
        assert limit - ratio > 0.05, (
            f"locality {ratio:.4f} clears {limit:.3f} by only {limit - ratio:.4f}, "
            "which upstream adding a few scenes would erase")


def check_row_group_size_above_cap_raises() -> None:
    """Calling with row_group_size above the cap must raise SystemExit."""
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "items.parquet"
        try:
            mosaic.write_items_parquet(_items(10), out, row_group_size=999_777)
            raise AssertionError("expected SystemExit to be raised")
        except SystemExit as exc:
            message = str(exc)
            assert "999777" in message, f"expected 999777 in message, got {message}"


if __name__ == "__main__":
    print("check_items_parquet.py")
    check("row count matches item count", check_row_count_matches_items)
    check("several row groups are written", check_multiple_row_groups)
    check("row groups stay within the 150k cap", check_row_groups_within_cap)
    check("rows are spatially ordered", check_rows_are_spatially_ordered)
    check("the default row group size keeps locality margin",
          check_default_row_group_size_keeps_locality_margin)
    check("row group size above cap raises", check_row_group_size_above_cap_raises)
    if FAILURES:
        raise SystemExit(f"{len(FAILURES)} failure(s)")
    print("all ok")
