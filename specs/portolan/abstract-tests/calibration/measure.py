# /// script
# requires-python = ">=3.11"
# dependencies = ["pyarrow>=21", "fsspec>=2024.6", "aiohttp>=3.9"]
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


def file_boxes(path: Path | str) -> tuple[list[Box], list[float], list[float]] | str:
    """Per-row-group boxes, rows and compressed bytes, or why the file has none."""
    import pyarrow.parquet as pq

    parquet = pq.ParquetFile(_open(path))
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


SIZE_FLOOR = 5_000_000
PASS_BAR = 0.65
CLEAR_FAIL_BAR = 0.25
PASS_FLOOR = 8
USER_AGENT = "portolan-calibration/1 (+https://github.com/portolan-sdi/portolan-spec)"
COLUMNS = [
    "catalog",
    "collection",
    "file",
    "row_groups",
    "rows",
    "compressed_bytes",
    "achieved",
    "achievable",
    "efficiency",
    "area_sum",
    "efficiency_extent_window",
    "verdict",
    "note",
]


def _open(path: Path | str):
    """A local path as is, or a remote file that fsspec reads by range requests."""
    if isinstance(path, str) and path.startswith(("http://", "https://")):
        import fsspec

        return fsspec.open(path, "rb", block_size=1 << 20).open()
    return path


def extent_window_skip(boxes: list[Box]) -> float:
    """The skip rate under the earlier draft, for comparison only.

    That draft sized the window at 10% of each side of the extent, placed its
    corner uniformly so the window stays inside the extent, and counted every
    row group once. This is its closed form.
    """
    e = union(boxes)
    w = QUERY_FRACTION * (e[2] - e[0])
    h = QUERY_FRACTION * (e[3] - e[1])

    def axis(lo: float, hi: float, b0: float, b1: float, size: float) -> float:
        span = hi - lo - size
        if span <= 0:
            return 1.0
        return max(0.0, min(b1, hi - size) - max(b0 - size, lo)) / span

    hits = [axis(e[0], e[2], b[0], b[2], w) * axis(e[1], e[3], b[1], b[3], h) for b in boxes]
    return 1.0 - sum(hits) / len(hits)


def extent_window_efficiency(boxes: list[Box]) -> float | None:
    achievable = extent_window_skip(grid(len(boxes), union(boxes)))
    if achievable <= ZERO_SKIP_TOLERANCE:
        return None
    return min(1.0, max(0.0, extent_window_skip(boxes)) / achievable)


def verdict(count: int, size: int, efficiency: float | None) -> str:
    """The footer check's outcome under the spatial-ordering rule in formats.md."""
    if size < SIZE_FLOOR:
        return "too-small"
    if efficiency is None:
        return "row-check"
    if count >= PASS_FLOOR:
        return "pass" if efficiency >= PASS_BAR else "fail"
    if count >= 3 and efficiency < CLEAR_FAIL_BAR:
        return "fail"
    return "row-check"


def measure_one(path: Path | str) -> dict:
    """One CSV row for one file, with the reason when the file has no score."""
    row = {column: "" for column in COLUMNS}
    row["file"] = str(path)
    try:
        result = file_boxes(path)
    except Exception as exc:  # noqa: BLE001 - a corpus survey reports and moves on
        row["note"] = f"unreadable: {type(exc).__name__}: {exc}"[:300]
        return row
    if isinstance(result, str):
        row["note"] = result
        return row
    boxes, rows, sizes = result
    s = score(boxes, rows, sizes)
    old = extent_window_efficiency(boxes)
    size = int(sum(sizes))
    row.update(
        row_groups=s["count"],
        rows=int(sum(rows)),
        compressed_bytes=size,
        achieved=f"{s['achieved']:.6f}",
        achievable=f"{s['achievable']:.6f}",
        efficiency="" if s["efficiency"] is None else f"{s['efficiency']:.6f}",
        area_sum="" if s["area_sum"] is None else f"{s['area_sum']:.6f}",
        efficiency_extent_window="" if old is None else f"{old:.6f}",
        verdict=verdict(s["count"], size, s["efficiency"]),
    )
    return row


def _write(rows: list[dict], out: Path) -> None:
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def measure(root: Path, out: Path) -> None:
    files = sorted(root.rglob("*.parquet"))
    _write([measure_one(path) for path in files], out)
    print(f"wrote {out} ({len(files)} files)")


def _fetch_json(url: str) -> dict:
    import urllib.request

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def _is_data_parquet(asset: dict) -> bool:
    from urllib.parse import urlparse

    kind = str(asset.get("type", "")).lower()
    href = str(asset.get("href", ""))
    is_parquet = "parquet" in kind or urlparse(href).path.endswith(".parquet")
    roles = asset.get("roles")
    return is_parquet and (not roles or "data" in roles)


def measure_registry(registry: Path, out: Path, per_collection: int, workers: int) -> None:
    """Measure every catalog listed in a checkout of portolan-registry.

    One thread pool fetches STAC objects for all catalogs at once, and a second
    pool reads Parquet footers as soon as the crawl finds a file. Inside a
    collection the crawl follows at most ``per_collection`` item links and
    ``per_collection`` child links per object, so a partitioned collection with
    thousands of items costs a few requests, not thousands. A ``partition:glob``
    href names no single file, so the crawl measures the items instead.
    """
    import re
    import time
    from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
    from urllib.parse import urljoin

    catalogs: list[tuple[str, str]] = []
    for entry in sorted((registry / "catalogs").glob("*.yaml")):
        match = re.search(r"^url:\s*(\S+)", entry.read_text(), re.M)
        if match:
            catalogs.append((entry.stem, match.group(1).strip("'\"")))

    fetch_pool = ThreadPoolExecutor(workers)
    footer_pool = ThreadPoolExecutor(workers)
    pending: dict = {}
    footers: list = []
    seen: set[str] = set()
    counts: dict[tuple[str, str], int] = {}
    fetched = errors = 0
    last_report = time.monotonic()

    def follow(catalog: str, url: str, collection: str) -> None:
        if url not in seen:
            seen.add(url)
            pending[fetch_pool.submit(_fetch_json, url)] = (catalog, url, collection)

    def footer(catalog: str, collection: str, url: str) -> dict:
        row = measure_one(url)
        row.update(catalog=catalog, collection=collection)
        return row

    for name, url in catalogs:
        follow(name, url, "")
    while pending:
        done, _ = wait(pending, timeout=5, return_when=FIRST_COMPLETED)
        for future in done:
            catalog, url, collection = pending.pop(future)
            try:
                obj = future.result()
            except Exception as exc:  # noqa: BLE001 - a survey reports and moves on
                errors += 1
                print(f"crawl {catalog}: {url}: {type(exc).__name__}: {exc}"[:300], file=sys.stderr)
                continue
            fetched += 1
            if obj.get("type") == "Collection":
                collection = obj.get("id", collection)
            key = (catalog, collection)
            for asset in (obj.get("assets") or {}).values():
                href = urljoin(url, str(asset.get("href", "")))
                if not _is_data_parquet(asset) or "*" in href or href in seen:
                    continue
                if not href.startswith(("http://", "https://")):
                    print(f"crawl {catalog}: {href}: not an http(s) href", file=sys.stderr)
                    continue
                if counts.get(key, 0) < per_collection:
                    seen.add(href)
                    counts[key] = counts.get(key, 0) + 1
                    footers.append(footer_pool.submit(footer, catalog, collection, href))
            links = obj.get("links") or []
            items = [link for link in links if link.get("rel") == "item"]
            children = [link for link in links if link.get("rel") == "child"]
            if collection:
                items = items[: max(0, per_collection - counts.get(key, 0))]
                children = children[:per_collection]
            for link in children + items:
                follow(catalog, urljoin(url, link["href"]), collection)
        if time.monotonic() - last_report > 10:
            last_report = time.monotonic()
            finished = sum(f.done() for f in footers)
            print(
                f"objects {fetched} (errors {errors}, queued {len(pending)}); "
                f"footers {finished}/{len(footers)}",
                file=sys.stderr,
                flush=True,
            )
    fetch_pool.shutdown()
    rows = [f.result() for f in footers]
    footer_pool.shutdown()
    _write(rows, out)
    print(f"wrote {out} ({len(rows)} files from {len(catalogs)} catalogs)")


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
        "--registry",
        type=Path,
        help="measure every catalog listed in this portolan-registry checkout",
    )
    parser.add_argument(
        "--per-collection",
        type=int,
        default=3,
        help="registry mode: the most files to measure in one collection",
    )
    parser.add_argument("--workers", type=int, default=16, help="registry mode: threads")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="reproduce the abstract test vectors and exit",
    )
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    if args.registry:
        measure_registry(args.registry, Path(args.out), args.per_collection, args.workers)
        return 0
    if not args.directory:
        parser.error("give a corpus directory, --registry, or --self-test")
    measure(Path(args.directory), Path(args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
