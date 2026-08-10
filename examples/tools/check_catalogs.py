# /// script
# requires-python = ">=3.12"
# ///
"""Validate every built example catalog with rashid, upstream sources included.

examples/catalog/ holds the built trees of every example catalog this repo
publishes. portolan-reference is committed in full, Parquet and COG included,
and is the canonical worked example. naip-mosaic is not committed, it is
gitignored, so it is present only when something built it first.
publish-catalogs.yaml does exactly that, building each manifest and then gating
it here. The weekly catalog-upstream.yaml run builds nothing, so it no longer
covers that catalog at all. This runs rashid over whichever trees are present.

The data pass runs at full scope by default, which is what separates this check
from the generator checks under examples/tools/tests/. Those read the committed
bytes through a local-only reader and stay offline. This one refetches the
stable upstream sources and proves the file:size and file:checksum published for
each. Spec issue #80 was an upstream drifting away from a published checksum,
and nothing else catches that.

A baseline may narrow that with a data_scope field. "local" runs every data rule
but treats a remote href as unfetchable, which is what naip-mosaic needs, since
its assets are 1.86 TB of COGs hosted elsewhere. Narrowing the scope is not the
same as skipping the pass, the local assets are still fully checked.

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
    uv run examples/tools/check_catalogs.py --catalog portolan-reference
"""

from __future__ import annotations

import argparse
import fnmatch
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


def load_baseline(root: Path, catalog: Path) -> dict:
    """The accepted-findings baseline for one catalog, or an empty dict.

    A catalog with no baseline stays at zero tolerance, which is where
    portolan-reference sits. JSON rather than YAML so this script keeps running
    on the standard library alone.
    """
    path = root / "examples/expected-findings" / f"{catalog.name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def path_matches(path: str, pattern: str) -> bool:
    """Glob a finding path segment by segment, so `*` never crosses a `/`.

    fnmatch over the whole string would let `imagery/*/item.json` match a path
    nested any number of directories deeper, which is the opposite of what an
    entry scoping a rule to one place is asking for.
    """
    parts = path.split("/")
    globs = pattern.split("/")
    if len(parts) != len(globs):
        return False
    return all(fnmatch.fnmatchcase(part, glob)
               for part, glob in zip(parts, globs, strict=True))


def apply_baseline(data: dict, baseline: dict) -> tuple[list[dict], list[str]]:
    """Findings the baseline does not accept, and why the gate should fail.

    Accepting a rule is not silencing it. Four things line up before a finding
    counts as known, and any one of them missing fails the gate.

    The rule has to be named. The finding's path has to match the entry's
    `path_glob`, so a rule accepted for 1848 remote assets cannot also excuse
    itself on a local file the publisher does host. The severity has to be the
    one the entry declares, so a rule promoted from warning to error reads as a
    regression rather than a match. And the message has to match `message_glob`.

    The tally is an exact `count` rather than a ceiling, and it fails in both
    directions on purpose. Upward, a second asset losing its checksum is a new
    defect a ceiling would swallow. Downward, an upstream search returning fewer
    scenes than it should would let publish_catalogs.py replace a good published
    catalog with a gutted one through `s5cmd sync --delete`, and a ceiling can
    never see that at all.

    `message_glob` separates what the count cannot. A rule usually covers more
    than one defect, PTL-AST-003 covers an absent checksum and a malformed
    file:size both, and an asset that swapped one for the other still reports
    once. Only the message moves, so only the message can fail it.
    """
    accepted = {entry["rule"]: entry for entry in baseline.get("accepted", [])}
    counts: dict[str, int] = {rule: 0 for rule in accepted}
    unexpected: list[dict] = []
    for finding in data["findings"]:
        if finding["severity"] == "info":
            continue
        entry = accepted.get(finding["rule_id"])
        if (entry is not None
                and finding["severity"] == entry["severity"]
                and path_matches(finding["path"], entry["path_glob"])
                and fnmatch.fnmatchcase(finding["message"], entry["message_glob"])):
            counts[finding["rule_id"]] += 1
        else:
            unexpected.append(finding)

    reasons = [
        f"{f['rule_id']} {f['severity']} at {f['path']} is not accepted by the "
        f"baseline, {f['message']}"
        for f in unexpected
    ]
    reasons += [
        f"{rule} occurred {seen} times, and the baseline expects exactly "
        f"{accepted[rule]['count']}"
        for rule, seen in sorted(counts.items())
        if seen != accepted[rule]["count"]
    ]
    return unexpected, reasons


# The data scopes a baseline may ask for. Absent means rashid's default pass,
# which reads every asset including remote ones. "local" runs every data rule
# but treats a remote href as unfetchable, which is what a metadata-only mirror
# needs. Anything else is a typo and must fail rather than silently widen the
# pass, so this is a closed set rather than a passthrough.
DATA_SCOPES = frozenset({"local"})


def run_rashid(requirement: str, catalog: Path, data_scope: str | None = None) -> dict:
    """rashid's JSON report for one catalog tree.

    data_scope of None runs the default data pass. "local" adds
    --data-scope local, so every data rule still runs but only against assets
    inside the catalog tree.
    """
    if data_scope is not None and data_scope not in DATA_SCOPES:
        raise SystemExit(
            f"{catalog.name}: unknown data_scope {data_scope!r}, "
            f"expected one of {sorted(DATA_SCOPES)} or the field omitted")
    cmd = ["uv", "run", "--with", requirement,
           "rashid", "check", "--schema", "--all", "--json", str(catalog)]
    if data_scope is not None:
        cmd += ["--data-scope", data_scope]
    completed = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if not completed.stdout.strip():
        sys.stderr.write(completed.stderr)
        raise SystemExit(f"rashid produced no report for {catalog}")
    return json.loads(completed.stdout)


def report(catalog: Path, data: dict, root: Path, baseline: dict) -> bool:
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
    if not baseline:
        print("::endgroup::")
        return data["error_count"] + data["warning_count"] == 0
    _, reasons = apply_baseline(data, baseline)
    # The expected counts print alongside the rule names because they are what a
    # reader has to copy back into the baseline when upstream legitimately gains
    # or loses a scene.
    accepted = ", ".join(
        f"{e['rule']} x{e['count']}"
        for e in sorted(baseline.get("accepted", []), key=lambda e: e["rule"]))
    scope = baseline.get("data_scope")
    print(f"  baseline accepts {accepted}, "
          f"data scope {scope if scope else 'full'}.")
    for reason in reasons:
        print(f"  UNEXPECTED {reason}")
    print("::endgroup::")
    return not reasons


def write_step_summary(rows: list[tuple[Path, dict, bool]]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    # Result is the first column because a baselined catalog reports thousands of
    # accepted errors, and a count with no verdict beside it reads as a failure to
    # anyone scanning the run.
    lines = [
        "| Catalog | Result | Errors | Warnings | Infos | Files |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    lines += [
        f"| `{catalog.name}` | {'pass' if ok else '**fail**'} "
        f"| {data['error_count']} | {data['warning_count']} "
        f"| {data['info_count']} | {data['files_checked']} |"
        for catalog, data, ok in rows
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
        manifest = root / "examples/manifests" / f"{args.catalog}.yaml"
        if args.catalog and manifest.exists():
            raise SystemExit(
                f"{args.catalog} has a manifest but no built tree. Build it "
                f"first with 'uv run examples/tools/build.py --catalog {args.catalog}'."
            )
        raise SystemExit(f"no catalogs found under {root / 'examples/catalog'}")

    rows = []
    for catalog in trees:
        baseline = load_baseline(root, catalog)
        data = run_rashid(requirement, catalog, data_scope=baseline.get("data_scope"))
        rows.append((catalog, data, report(catalog, data, root, baseline)))

    write_step_summary(rows)

    failed = [catalog for catalog, _, ok in rows if not ok]
    for catalog in failed:
        print(
            f"::error::{catalog.relative_to(root)} no longer validates. Rebuild it with "
            f"'uv run examples/tools/build.py --catalog {catalog.name}'. Commit the "
            f"result only if this catalog's tree is tracked, naip-mosaic's is not."
        )
    print(f"\n{len(rows) - len(failed)}/{len(rows)} catalogs passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
