# /// script
# requires-python = ">=3.11"
# dependencies = ["pyarrow>=21"]
# ///
"""Measure the pruning-efficiency metric over a corpus of Parquet files.

A direct transcription of the spatial-ordering rule in formats.md: the query
window's centre falls in row group i with probability rows_i / N, uniform in
its box, and spans 10% of each dimension of that box; each group weighs its
compressed bytes; the reference is the near-square grid with uniform weights.
Footer-only. ``--self-test`` reproduces every layout vector in
``../spatial-metric-vectors.json``.

Usage::

    uv run specs/portolan/abstract-tests/calibration/measure.py <dir> --out results.csv
    uv run specs/portolan/abstract-tests/calibration/measure.py --self-test
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

QUERY_FRACTION = 0.10
ZERO_SKIP_TOLERANCE = 1e-9

Box = tuple[float, float, float, float]


def axis_factor(a0: float, a1: float, g0: float, g1: float, half: float) -> float:
    """P(centre coordinate uniform on [a0, a1] lands in [g0 - half, g1 + half])."""
    g0, g1 = g0 - half, g1 + half
    if a1 <= a0:
        return 1.0 if g0 <= a0 <= g1 else 0.0
    return min(1.0, max(0.0, (min(a1, g1) - max(a0, g0)) / (a1 - a0)))


def union(boxes: list[Box]) -> Box:
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def skip_rate(
    boxes: list[Box],
    rows: list[float] | None = None,
    sizes: list[float] | None = None,
) -> float:
    rows = rows if rows is not None else [1.0] * len(boxes)
    sizes = sizes if sizes is not None else list(rows)
    total_rows = sum(rows)
    total_size = sum(sizes)
    read = 0.0
    for j, target in enumerate(boxes):
        hit = 0.0
        for i, source in enumerate(boxes):
            half_w = QUERY_FRACTION * (source[2] - source[0]) / 2.0
            half_h = QUERY_FRACTION * (source[3] - source[1]) / 2.0
            fx = axis_factor(source[0], source[2], target[0], target[2], half_w)
            fy = axis_factor(source[1], source[3], target[1], target[3], half_h)
            hit += rows[i] / total_rows * fx * fy
        read += sizes[j] / total_size * hit
    rate = 1.0 - read
    if abs(rate) <= ZERO_SKIP_TOLERANCE:
        return 0.0
    return min(1.0, max(0.0, rate))


def grid(n: int, e: Box) -> list[Box]:
    cols = math.ceil(math.sqrt(n))
    grows = math.ceil(n / cols)
    cells: list[Box] = []
    height = (e[3] - e[1]) / grows
    for r in range(grows):
        row_cols = cols if r < grows - 1 else n - cols * (grows - 1)
        width = (e[2] - e[0]) / row_cols
        for c in range(row_cols):
            cells.append(
                (
                    e[0] + c * width,
                    e[1] + r * height,
                    e[0] + (c + 1) * width,
                    e[1] + (r + 1) * height,
                )
            )
    return cells


def score(
    boxes: list[Box],
    rows: list[float] | None = None,
    sizes: list[float] | None = None,
) -> dict:
    e = union(boxes)
    achieved = skip_rate(boxes, rows, sizes)
    achievable = skip_rate(grid(len(boxes), e))
    efficiency = (
        min(1.0, achieved / achievable) if achievable > ZERO_SKIP_TOLERANCE else None
    )
    extent_area = (e[2] - e[0]) * (e[3] - e[1])
    area_sum = (
        sum((b[2] - b[0]) * (b[3] - b[1]) for b in boxes) / extent_area
        if extent_area > 0
        else None
    )
    return {
        "count": len(boxes),
        "achieved": achieved,
        "achievable": achievable,
        "efficiency": efficiency,
        "area_sum": area_sum,
    }


def _covering_leaves(geo: dict) -> dict[str, str] | None:
    primary = geo.get("primary_column")
    columns = geo.get("columns") or {}
    covering = (columns.get(primary) or {}).get("covering") or {}
    bbox = covering.get("bbox")
    if not isinstance(bbox, dict):
        return None
    try:
        return {corner: ".".join(bbox[corner]) for corner in ("xmin", "ymin", "xmax", "ymax")}
    except (KeyError, TypeError):
        return None


def file_boxes(path: Path) -> tuple[list[Box], list[float], list[float]] | str:
    """Per-row-group boxes, rows and compressed bytes, or why the file has none."""
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(path)
    meta = parquet.metadata
    raw = (parquet.schema_arrow.metadata or {}).get(b"geo")
    geo = json.loads(raw) if raw else {}
    group0 = meta.row_group(0) if meta.num_row_groups else None
    index = (
        {group0.column(j).path_in_schema: j for j in range(group0.num_columns)} if group0 else {}
    )

    def group_weights(i: int) -> tuple[float, float]:
        group = meta.row_group(i)
        compressed = sum(
            group.column(j).total_compressed_size for j in range(group.num_columns)
        )
        return float(group.num_rows), float(compressed)

    leaves = _covering_leaves(geo) if geo else None
    boxes: list[Box] = []
    if leaves and all(path_ in index for path_ in leaves.values()):
        for i in range(meta.num_row_groups):
            group = meta.row_group(i)
            stats = {c: group.column(index[p]).statistics for c, p in leaves.items()}
            if any(s is None or s.min is None for s in stats.values()):
                boxes = []
                break
            boxes.append(
                (
                    float(stats["xmin"].min),
                    float(stats["ymin"].min),
                    float(stats["xmax"].max),
                    float(stats["ymax"].max),
                )
            )
    if not boxes:
        primary = geo.get("primary_column") or "geometry"
        j = index.get(primary)
        if j is None:
            return "no-statistics"
        for i in range(meta.num_row_groups):
            geo_stats = getattr(meta.row_group(i).column(j), "geo_statistics", None)
            if geo_stats is None or geo_stats.xmin is None:
                return "no-statistics"
            boxes.append(
                (
                    float(geo_stats.xmin),
                    float(geo_stats.ymin),
                    float(geo_stats.xmax),
                    float(geo_stats.ymax),
                )
            )
    if not all(math.isfinite(v) for b in boxes for v in b):
        return "non-finite-statistics"
    weights = [group_weights(i) for i in range(meta.num_row_groups)]
    return boxes, [w[0] for w in weights], [w[1] for w in weights]


def measure(root: Path, out: Path) -> None:
    files = sorted(root.rglob("*.parquet"))
    with out.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "file",
                "row_groups",
                "compressed_bytes",
                "achieved",
                "achievable",
                "efficiency",
                "area_sum",
                "note",
            ]
        )
        for path in files:
            try:
                result = file_boxes(path)
            except Exception as exc:  # noqa: BLE001 - a corpus survey reports and moves on
                writer.writerow([path, "", "", "", "", "", "", f"unreadable: {exc}"])
                continue
            if isinstance(result, str):
                writer.writerow([path, "", "", "", "", "", "", result])
                continue
            boxes, rows, sizes = result
            s = score(boxes, rows, sizes)
            writer.writerow(
                [
                    path,
                    s["count"],
                    int(sum(sizes)),
                    f"{s['achieved']:.6f}",
                    f"{s['achievable']:.6f}",
                    "" if s["efficiency"] is None else f"{s['efficiency']:.6f}",
                    "" if s["area_sum"] is None else f"{s['area_sum']:.6f}",
                    "",
                ]
            )
    print(f"wrote {out} ({len(files)} files)")


def self_test() -> int:
    vectors = json.loads(
        (Path(__file__).parent.parent / "spatial-metric-vectors.json").read_text()
    )
    failures = 0
    for name, vector in vectors["layouts"].items():
        boxes = [tuple(b) for b in vector["boxes"]]
        rows = [float(r) for r in vector["rows"]] if "rows" in vector else None
        sizes = [float(x) for x in vector["sizes"]] if "sizes" in vector else None
        got = score(boxes, rows, sizes)
        expected = vector["expected"]
        checks = [
            abs(got["achieved"] - expected["achieved"]) < 1e-6,
            abs(got["achievable"] - expected["achievable"]) < 1e-6,
            (got["efficiency"] is None) == (expected["efficiency"] is None),
            expected["efficiency"] is None
            or abs(got["efficiency"] - expected["efficiency"]) < 1e-6,
            (got["area_sum"] is None) == (expected["area_sum"] is None),
            expected["area_sum"] is None or abs(got["area_sum"] - expected["area_sum"]) < 1e-5,
        ]
        status = "OK " if all(checks) else "BAD"
        failures += not all(checks)
        print(f"{status} {name}")
    print("ALL MATCH" if not failures else f"{failures} mismatches")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", help="corpus root to measure")
    parser.add_argument("--out", default="results.csv", help="CSV to write")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="reproduce the abstract test vectors and exit",
    )
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if not args.directory:
        parser.error("a corpus directory is required without --self-test")
    measure(Path(args.directory), Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
