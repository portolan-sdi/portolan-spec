# /// script
# requires-python = ">=3.12"
# ///
"""Validate every committed example catalog with rashid, upstream sources included.

examples/catalog/ holds the canonical examples of a conformant Portolan catalog,
committed in full, Parquet and COG included. This runs rashid over each of them.

The data pass is left on, which is what separates this check from the generator
checks under examples/tools/tests/. Those read the committed bytes through a
local-only reader and stay offline. This one refetches the stable upstream
sources and proves the file:size and file:checksum published for each. Spec
issue #80 was an upstream drifting away from a published checksum, and nothing
else catches that.

That makes this check depend on third-party servers, so it belongs on a schedule
rather than on a pull request. A source being briefly unreachable is not a reason
to block a merge, but it is a reason to look.

The rashid version is read out of the PEP 723 header in examples/tools/build.py,
so the validator that checks a catalog is the validator that built it. This
script declares no dependencies of its own for that reason, and runs on the
standard library alone.

The gate is errors and warnings. rashid's own exit code fires on errors only, and
a warning is a real defect in a reference example. Infos are advisory and do not
fail the run. The reference catalog reports eight PTL-PRO-002 infos, which are
expected and terminal, see examples/tools/CLAUDE.md.

Usage::

    uv run examples/tools/check_catalogs.py
    uv run examples/tools/check_catalogs.py --catalog reference
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

# The reference regex from PEP 723 for locating an embedded metadata block.
PEP_723_BLOCK = (
    r"(?m)^# /// (?P<type>[a-zA-Z0-9-]+)$\s(?P<content>(^#(| .*)$\s)+)^# ///$"
)


def _repo_root() -> Path:
    # examples/tools/check_catalogs.py -> repo root is three levels up
    return Path(__file__).resolve().parent.parent.parent


def script_dependencies(script: Path) -> list[str]:
    """The PEP 723 `dependencies` list declared by a uv entrypoint script."""
    matches = [
        match
        for match in re.finditer(PEP_723_BLOCK, script.read_text(encoding="utf-8"))
        if match.group("type") == "script"
    ]
    if len(matches) != 1:
        raise SystemExit(f"{script}: expected exactly one PEP 723 script block")
    content = "".join(
        line[2:] if line.startswith("# ") else line[1:]
        for line in matches[0].group("content").splitlines(keepends=True)
    )
    deps = tomllib.loads(content).get("dependencies", [])
    return [str(dep) for dep in deps]


def rashid_requirement(build_script: Path) -> str:
    """The rashid requirement string pinned by the generator entrypoint."""
    for dep in script_dependencies(build_script):
        if re.match(r"^rashid\b", dep):
            return dep
    raise SystemExit(f"{build_script}: no rashid dependency in its PEP 723 header")


def catalogs(root: Path, only: str | None) -> list[Path]:
    """Every built catalog tree under examples/catalog/, by root catalog.json."""
    found = sorted(
        path.parent
        for path in root.glob("examples/catalog/*/catalog.json")
    )
    if only:
        found = [path for path in found if path.name == only]
    return found


def run_rashid(requirement: str, catalog: Path) -> dict:
    """rashid's JSON report for one catalog tree."""
    completed = subprocess.run(
        [
            "uv", "run", "--with", requirement,
            "rashid", "check", "--schema", "--all", "--json", str(catalog),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if not completed.stdout.strip():
        sys.stderr.write(completed.stderr)
        raise SystemExit(f"rashid produced no report for {catalog}")
    return json.loads(completed.stdout)


def report(catalog: Path, data: dict, root: Path) -> bool:
    """Print one catalog's findings. True when it passes the gate."""
    print(f"::group::{catalog.relative_to(root)}")
    for finding in data["findings"]:
        print(
            f"  {finding['severity']:<7} {finding['rule_id']}  "
            f"{finding['path']}: {finding['message']}"
        )
    print(
        f"  {data['error_count']} error(s), {data['warning_count']} warning(s), "
        f"{data['info_count']} info(s) across {data['files_checked']} files."
    )
    print("::endgroup::")
    return data["error_count"] + data["warning_count"] == 0


def write_step_summary(rows: list[tuple[Path, dict, bool]]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = [
        "| Catalog | Errors | Warnings | Infos | Files |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| `{catalog.name}` | {data['error_count']} | {data['warning_count']} "
        f"| {data['info_count']} | {data['files_checked']} |"
        for catalog, data, _ in rows
    ]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    root = _repo_root()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", default=None, help="check only this catalog by directory name")
    args = parser.parse_args()

    requirement = rashid_requirement(root / "examples/tools/build.py")
    print(f"rashid requirement: {requirement}")

    trees = catalogs(root, args.catalog)
    if not trees:
        raise SystemExit(f"no catalogs found under {root / 'examples/catalog'}")

    rows = []
    for catalog in trees:
        data = run_rashid(requirement, catalog)
        rows.append((catalog, data, report(catalog, data, root)))

    write_step_summary(rows)

    failed = [catalog for catalog, _, ok in rows if not ok]
    for catalog in failed:
        print(
            f"::error::{catalog.relative_to(root)} no longer validates. Rebuild it with "
            f"'uv run examples/tools/build.py --catalog {catalog.name}' and commit the result."
        )
    print(f"\n{len(rows) - len(failed)}/{len(rows)} catalogs passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
