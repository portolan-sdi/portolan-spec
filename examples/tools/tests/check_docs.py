# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "duckdb>=1.5.5",
#   "pandas>=2.2",
#   "pyarrow>=25",
#   "geopandas>=1.1",
#   "rioxarray>=0.17",
#   "rasterio>=1.5",
# ]
# ///
"""Run every fenced code block in the committed catalog docs.

The documentation best-practices page asks that every example be run before
publishing, because a broken Quick Start costs more trust than no Quick Start,
and the most common defect in otherwise strong catalogs is prose that drifted
from the data. This check makes that rule mechanical. It walks every README.md
and AGENTS.md under examples/catalog/, extracts the ```sql and ```python
fences, and executes each one with the doc's own directory as the working
directory, exactly as a reader following along would.

Blocks that reference a URL are skipped so the suite stays offline and
deterministic, the weekly upstream workflow covers the network. Other
languages (bash, json) are skipped as illustration.

Run: uv run examples/tools/tests/check_docs.py
"""
import re
import subprocess
import sys
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent.parent.parent
CATALOGS = ROOT / "examples/catalog"

FENCE = re.compile(r"^```(\w+)\n(.*?)^```", re.MULTILINE | re.DOTALL)
RUNNABLE = {"sql", "python"}


def blocks(md: Path) -> list[tuple[str, str]]:
    return [(m.group(1), m.group(2)) for m in FENCE.finditer(md.read_text())]


def run_sql(code: str, cwd: Path) -> str | None:
    con = duckdb.connect()
    try:
        con.execute(f"SET file_search_path = '{cwd}'")
        con.execute(code)
        return None
    except Exception as e:  # noqa: BLE001 - report every failure mode the same way
        return str(e)
    finally:
        con.close()


def run_python(code: str, cwd: Path) -> str | None:
    r = subprocess.run([sys.executable, "-c", code], cwd=cwd,
                       capture_output=True, text=True, timeout=120)
    return None if r.returncode == 0 else (r.stderr.strip() or r.stdout.strip())


def main() -> int:
    docs = sorted(list(CATALOGS.rglob("README.md")) + list(CATALOGS.rglob("AGENTS.md")))
    if not docs:
        print("FAIL no docs found under examples/catalog/")
        return 1
    ran = skipped = 0
    failures: list[str] = []
    for md in docs:
        for i, (lang, code) in enumerate(blocks(md), start=1):
            where = f"{md.relative_to(ROOT)} block {i} ({lang})"
            if lang not in RUNNABLE or "http://" in code or "https://" in code:
                skipped += 1
                continue
            err = run_sql(code, md.parent) if lang == "sql" else run_python(code, md.parent)
            ran += 1
            if err:
                first = next((ln for ln in err.splitlines() if ln.strip()), err)
                failures.append(f"{where}\n    {first}")
    for f in failures:
        print(f"FAIL {f}")
    print(f"docs code blocks, {ran} ran, {skipped} skipped as illustrative, "
          f"{len(failures)} failed")
    if not failures and ran == 0:
        print("FAIL nothing ran, the docs carry no runnable blocks at all")
        return 1
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
