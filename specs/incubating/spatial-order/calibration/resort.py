# /// script
# requires-python = ">=3.11"
# dependencies = ["pyarrow>=21", "fsspec>=2024.6", "aiohttp>=3.9"]
# ///
"""Sort survey files with low efficiency and measure the copies.

The sorted copies form a positive control for the pass bar.
The script selects eligible files from a ``measure.py`` CSV.
Each file must score below ``--below`` and meet the ``--max-bytes`` limit.
For each file, ``gpio sort hilbert`` writes a Hilbert-sorted copy.
The copy uses the same number of rows per row group.
The script then measures it with the code from ``measure.py``.
A suitable bar lets sorted copies pass and rejects files with poor order.

The ``gpio`` command must be on the PATH.
Use ``uv tool install geoparquet-io`` to install it.

Usage::

    uv run specs/incubating/spatial-order/calibration/resort.py results.csv \\
        --out resort.csv --below 0.80 --max-bytes 300000000
"""

from __future__ import annotations

import argparse
import csv
import math
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from measure import USER_AGENT, measure_one  # noqa: E402

COLUMNS = [
    "catalog",
    "collection",
    "file",
    "row_groups",
    "rows",
    "compressed_bytes",
    "efficiency",
    "sorted_row_groups",
    "sorted_efficiency",
    "sorted_area_sum",
    "area_sum",
    "sorted_verdict",
    "note",
]


def resort(row: dict, workdir: Path) -> dict:
    out = {column: row.get(column, "") for column in COLUMNS}
    groups = int(row["row_groups"])
    rows = int(row["rows"])
    per_group = max(1, math.ceil(rows / groups))
    stem = f"{abs(hash(row['file']))}"
    source = workdir / f"{stem}-source.parquet"
    target = workdir / f"{stem}-sorted.parquet"
    # Sort a local copy with a plain name.
    # gpio interprets a path segment such as country=CA as a Hive partition.
    try:
        request = urllib.request.Request(row["file"], headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=120) as response, source.open("wb") as f:
            shutil.copyfileobj(response, f, 1 << 20)
    except Exception as exc:  # noqa: BLE001 - report each error and continue
        source.unlink(missing_ok=True)
        out["note"] = f"download failed: {type(exc).__name__}: {exc}"[:300]
        return out
    command = [
        "gpio",
        "sort",
        "hilbert",
        str(source),
        str(target),
        "--row-group-size",
        str(per_group),
        "--add-bbox",
        "--geoparquet-version",
        "1.1",
        "--write-memory",
        "2GB",
        "--overwrite",
    ]
    done = subprocess.run(command, capture_output=True, text=True, timeout=3600)
    source.unlink(missing_ok=True)
    if done.returncode != 0 or not target.exists():
        out["note"] = f"gpio failed: {(done.stderr or done.stdout).strip()[-300:]}"
        return out
    measured = measure_one(target)
    target.unlink(missing_ok=True)
    print(
        f"{row['efficiency'][:5]} -> {measured['efficiency'][:5]}  {row['file']}",
        file=sys.stderr,
        flush=True,
    )
    out.update(
        sorted_row_groups=measured["row_groups"],
        sorted_efficiency=measured["efficiency"],
        sorted_area_sum=measured["area_sum"],
        sorted_verdict=measured["verdict"],
        note=measured["note"],
    )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="a CSV that measure.py wrote")
    parser.add_argument("--out", type=Path, default=Path("resort.csv"))
    parser.add_argument(
        "--below", type=float, default=0.80, help="re-sort judged files under this efficiency"
    )
    parser.add_argument(
        "--max-bytes", type=int, default=300_000_000, help="skip files larger than this"
    )
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if shutil.which("gpio") is None:
        parser.error("gpio is not on the PATH; run `uv tool install geoparquet-io`")

    with args.results.open(newline="") as handle:
        rows = [
            r
            for r in csv.DictReader(handle)
            if r["efficiency"]
            and r["verdict"] != "too-small"
            and int(r["row_groups"]) >= 2
            and float(r["efficiency"]) < args.below
            and int(r["compressed_bytes"]) <= args.max_bytes
        ]
    with tempfile.TemporaryDirectory() as tmp, ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(lambda r: resort(r, Path(tmp)), rows))
    with args.out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(results)
    print(f"wrote {args.out} ({len(results)} files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
