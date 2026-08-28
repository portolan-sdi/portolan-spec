# /// script
# requires-python = ">=3.12"
# ///
"""Run every generator check in this directory and report them together.

Each check_*.py is its own uv entrypoint with its own PEP 723 dependencies, so
each runs in its own resolved environment. This runner shells out to `uv run`
per script rather than importing them, which keeps that isolation and means the
runner itself needs nothing but the standard library.

Every check here is offline and deterministic. check_tiles.py fetches from a
fake host, check_fetch.py runs against a local HTTP server, and check_validate.py
reads the committed catalog through validate.py's local-only reader. Nothing
reaches a third-party server, so this is safe to gate a pull request on. The
upstream sources are proven separately by examples/tools/check_catalogs.py.

Every check runs even after one fails, because a single failure should not hide
the other eight.

Usage::

    uv run examples/tools/tests/run_all.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
# examples/tools/tests/run_all.py -> repo root is three levels up
REPO = HERE.parent.parent.parent


def _checks() -> list[Path]:
    return sorted(HERE.glob("check_*.py"))


def main() -> int:
    checks = _checks()
    if not checks:
        print(f"no check_*.py found in {HERE}", file=sys.stderr)
        return 1

    results: list[tuple[str, bool, float]] = []
    for script in checks:
        print(f"::group::{script.name}", flush=True)
        started = time.monotonic()
        # check_validate.py pins rashid, and that pin bump lands in the same
        # pull request as the rashid release. A warm uv cache can hold a PyPI
        # index page from before that version exists. Refresh the one
        # package. See #155.
        completed = subprocess.run(
            ["uv", "run", "--refresh-package", "rashid", str(script)],
            check=False,
        )
        elapsed = time.monotonic() - started
        print("::endgroup::", flush=True)
        results.append((script.name, completed.returncode == 0, elapsed))

    print()
    for name, ok, elapsed in results:
        print(f"{'PASS' if ok else 'FAIL'}  {elapsed:5.1f}s  {name}")

    failed = [name for name, ok, _ in results if not ok]
    summary = (
        f"{len(results) - len(failed)}/{len(results)} generator checks passed"
        if not failed
        else f"{len(failed)} of {len(results)} generator checks failed: "
        + ", ".join(failed)
    )
    print(f"\n{summary}")

    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        lines = ["| Check | Result | Time |", "| --- | --- | --- |"]
        lines += [
            f"| `{name}` | {'pass' if ok else '**fail**'} | {elapsed:.1f}s |"
            for name, ok, elapsed in results
        ]
        with open(step_summary, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")

    if failed:
        rel = HERE.relative_to(REPO)
        for name in failed:
            print(f"::error::{name} failed, rerun it with 'uv run {rel}/{name}'")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
