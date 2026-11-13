# /// script
# requires-python = ">=3.11"
# dependencies = ["pyarrow>=21", "fsspec>=2024.6", "aiohttp>=3.9"]
# ///
"""Measure pruning efficiency for a corpus of Parquet files.

The script implements the spatial-order method in specs/incubating/spatial-order.md from footers.
It chooses row group i with probability rows_i / N.
It places the query window's center uniformly within that group's box.
The window spans 10% of each box dimension.
The skip rate weights each group by its compressed bytes.
The reference uses a near-square grid with uniform row and byte weights.
The ``--self-test`` option checks every layout vector in
``../spatial-metric-vectors.json``.

Usage::

    uv run specs/incubating/spatial-order/calibration/measure.py <dir> --out results.csv
    uv run specs/incubating/spatial-order/calibration/measure.py --self-test
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
    """Return the probability that a uniform center on [a0, a1] falls in [g0 - half, g1 + half]."""
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
    """Return row-group boxes, row counts, and compressed bytes, or explain why statistics are absent."""
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


PASS_BAR = 0.65
PASS_FLOOR = 8
ROW_FLOOR = 200
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
    """Return a local path or open a remote file with fsspec range requests."""
    if isinstance(path, str) and path.startswith(("http://", "https://")):
        import fsspec

        return fsspec.open(path, "rb", block_size=1 << 20).open()
    return path


def extent_window_skip(boxes: list[Box]) -> float:
    """Return the earlier draft's skip rate for comparison.

    That draft used a window at 10% of each extent dimension.
    It placed the corner uniformly where the window fits inside the extent.
    It gave every row group equal weight.
    This formula calculates that draft's rate without a random sample.
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
    """Return the footer verdict under the spatial-order method in specs/incubating/spatial-order.md.

    A file with eight or more row groups and a defined efficiency takes the
    footer check. Every other file takes the row check. ``size`` is unused
    since the 5 MB floor was retired, and stays for the CSV callers.
    """
    del size
    if count >= PASS_FLOOR and efficiency is not None:
        return "pass" if efficiency >= PASS_BAR else "fail"
    return "row-check"


def row_chunks(boxes: list) -> tuple[list[Box], list[float]]:
    """Split per-row boxes into the row-check chunks. None marks a row without a box."""
    n = len(boxes)
    chunks: list[Box] = []
    rows: list[float] = []
    for k in range(10):
        part = [b for b in boxes[(k * n) // 10 : ((k + 1) * n) // 10] if b is not None]
        if not part:
            continue
        chunks.append(union([tuple(b) for b in part]))
        rows.append(float(len(part)))
    return chunks, rows


def row_verdict(n_rows: int, efficiency: float | None) -> str:
    """Return the row-check verdict under the spatial-order method in specs/incubating/spatial-order.md."""
    if n_rows < ROW_FLOOR:
        return "too-few-rows"
    if efficiency is None:
        return "none"
    return "pass" if efficiency >= PASS_BAR else "fail"


def measure_one(path: Path | str) -> dict:
    """Return one CSV row per file and explain any absent score."""
    row = {column: "" for column in COLUMNS}
    row["file"] = str(path)
    try:
        result = file_boxes(path)
    except Exception as exc:  # noqa: BLE001 - report each file error and continue
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
    """Measure files from every catalog in a portolan-registry checkout.

    One thread pool fetches STAC objects across catalogs.
    A second pool reads Parquet footers as the crawl finds files.
    Within a collection, each object supplies at most ``per_collection`` item
    links and ``per_collection`` child links to follow.
    This cap limits requests for collections with thousands of partitions.
    A ``partition:glob`` href does not identify one file.
    The crawl measures the items instead.
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
            except Exception as exc:  # noqa: BLE001 - report each error and continue
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
            verdict(got["count"], 0, got["efficiency"]) == expected["verdict"],
        ]
        status = "OK " if all(checks) else "BAD"
        failures += not all(checks)
        print(f"{status} {name}")
    for name, vector in vectors["rows"].items():
        chunks, rows = row_chunks(vector["boxes"])
        got = score(chunks, rows, rows)
        expected = vector["expected"]
        checks = [
            [list(c) for c in chunks] == vector["expected_chunks"],
            rows == vector["chunk_rows"],
            abs(got["achieved"] - expected["achieved"]) < 1e-6,
            abs(got["achievable"] - expected["achievable"]) < 1e-6,
            expected["efficiency"] is None
            or abs(got["efficiency"] - expected["efficiency"]) < 1e-6,
            row_verdict(len(vector["boxes"]), got["efficiency"]) == expected["verdict"],
        ]
        status = "OK " if all(checks) else "BAD"
        failures += not all(checks)
        print(f"{status} rows/{name}")
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
