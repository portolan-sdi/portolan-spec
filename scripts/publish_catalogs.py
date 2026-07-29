# /// script
# requires-python = ">=3.12"
# ///
"""Publish a built example catalog to the Portolan repository on Source Cooperative.

examples/manifests/*.yaml each describe one whole catalog, and build.py turns a
manifest into a complete catalog tree under examples/catalog/<stem>/. This
uploads that tree to https://data.source.coop/portolan/portolan-pipeline/ so the
example is reachable at a real URL, which is the only way to exercise a Portolan
catalog the way a client actually reads one, over HTTP range requests.

The layout is <stem>/main/ for the default branch and <stem>/branches/<ref>/ for
anything else, so a branch can be previewed without touching what main
publishes. That mirrors the layout already in the bucket.

Transfers run through s5cmd rather than the AWS CLI. A catalog is a few hundred
small JSON files next to a handful of large Parquet and COG assets, and s5cmd
saturates that shape far better. `sync --delete` is scoped to one catalog's own
prefix, so a stale file from an earlier build is removed while everything else
published under portolan/portolan-pipeline/ is left alone.

After the upload it refetches the published catalog.json over HTTPS and checks
that it parses and still carries the id that was uploaded. A sync that reported
success but published nothing readable is the failure worth catching.

Usage::

    uv run scripts/publish_catalogs.py --list
    uv run scripts/publish_catalogs.py --catalog reference --dry-run
    uv run scripts/publish_catalogs.py --catalog reference
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

BUCKET = "s3://us-west-2.opendata.source.coop"
# The Source Cooperative repository. Both halves of this pair have to move
# together, they address the same bytes over S3 and over HTTPS.
REPO_PREFIX = "portolan/portolan-pipeline"
PUBLIC_BASE = "https://data.source.coop/portolan/portolan-pipeline"

DEFAULT_BRANCH = "main"
# Cloudflare fronts data.source.coop and 403s the default Python-urllib agent.
USER_AGENT = "portolan-spec-publish (+https://github.com/portolan-sdi/portolan-spec)"
# Finder litters the tree on macOS. It is gitignored, so CI never sees it, but a
# maintainer publishing from a working copy would otherwise ship it.
EXCLUDED_NAMES = {".DS_Store"}
# A ref becomes a URL path, so keep it to what is safe in one.
SAFE_REF = re.compile(r"^[A-Za-z0-9._/-]+$")


def _repo_root() -> Path:
    # scripts/publish_catalogs.py -> repo root is two levels up
    return Path(__file__).resolve().parent.parent


def manifest_stems(root: Path) -> list[str]:
    """Every catalog this repo knows how to build, by manifest file stem."""
    manifests = root / "examples/manifests"
    if not manifests.is_dir():
        return []
    return sorted(
        {path.stem for path in manifests.iterdir() if path.suffix in {".yaml", ".yml"}}
    )


def current_ref() -> str:
    """The branch being published from, in CI or in a working copy."""
    ref = os.environ.get("GITHUB_REF_NAME")
    if ref:
        return ref
    completed = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout.strip()


def ref_leaf(ref: str) -> str:
    """The prefix segment a ref publishes under."""
    if not SAFE_REF.match(ref) or ".." in ref:
        raise SystemExit(f"refusing to publish from ref {ref!r}, it is not path-safe")
    return DEFAULT_BRANCH if ref == DEFAULT_BRANCH else f"branches/{ref}"


def destination(catalog: str, leaf: str) -> tuple[str, str]:
    """The s3:// target and the public https:// URL for one catalog and ref."""
    if not catalog or "/" in catalog or ".." in catalog:
        raise SystemExit(f"refusing to publish catalog name {catalog!r}")
    tail = f"{REPO_PREFIX}/{catalog}/{leaf}"
    return f"{BUCKET}/{tail}/", f"{PUBLIC_BASE}/{catalog}/{leaf}/"


def tree_summary(tree: Path) -> tuple[int, int]:
    """File count and total bytes of a built catalog, as it will be published."""
    files = [
        path
        for path in tree.rglob("*")
        if path.is_file() and path.name not in EXCLUDED_NAMES
    ]
    return len(files), sum(path.stat().st_size for path in files)


def sync(tree: Path, target: str, dry_run: bool) -> None:
    """Mirror one built catalog tree onto its own prefix."""
    if shutil.which("s5cmd") is None:
        raise SystemExit("s5cmd is not on PATH, see https://github.com/peak/s5cmd")
    command = ["s5cmd"]
    if dry_run:
        command.append("--dry-run")
    command += [
        # A catalog is mostly small JSON, so the win is in request concurrency.
        "--numworkers", "64",
        "sync",
        # Scoped to this catalog's own prefix, so a file dropped from the
        # manifest disappears and nothing else in the bucket is touched.
        "--delete",
        # Without this a failed object is logged and the run still exits 0.
        "--exit-on-error",
    ]
    for name in sorted(EXCLUDED_NAMES):
        # A leading star, since the pattern is matched against the whole path.
        command += ["--exclude", f"*{name}"]
    command += [f"{tree}/", target]
    print(f"$ {' '.join(command)}")
    subprocess.run(command, check=True)


def verify(public_url: str, expected_id: str) -> None:
    """Refetch the published root over HTTPS and prove it is the one uploaded.

    Two things about data.source.coop are worth knowing here. It sits behind
    Cloudflare, which answers the default `Python-urllib/*` User-Agent with 403,
    so the request has to name itself. And an object read a moment after it is
    written can still miss at an edge, so a first failure is retried rather than
    reported.
    """
    url = f"{public_url}catalog.json"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    published: dict | None = None
    last: Exception | None = None
    for attempt, pause in enumerate((2, 5, 10), start=1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                published = json.load(response)
            break
        except (urllib.error.URLError, json.JSONDecodeError) as exc:
            last = exc
            print(f"  attempt {attempt}: {exc}, retrying in {pause}s")
            time.sleep(pause)
    if published is None:
        raise SystemExit(f"published catalog is not readable at {url}: {last}")
    if published.get("id") != expected_id:
        raise SystemExit(
            f"{url} has id {published.get('id')!r}, expected {expected_id!r}"
        )
    print(f"verified {url} (id {expected_id})")


def write_output(key: str, value: str) -> None:
    """Hand a value back to the workflow step that invoked this."""
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"{key}={value}\n")


def write_step_summary(rows: list[tuple[str, str, int, int]]) -> None:
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    lines = [
        "| Catalog | Files | Size | Published at |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| `{catalog}` | {count} | {size / 1_048_576:.1f} MiB | <{url}> |"
        for catalog, url, count, size in rows
    ]
    with open(path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    root = _repo_root()
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--catalog", default=None, help="publish only this manifest stem")
    parser.add_argument("--list", action="store_true", help="print the manifest stems as JSON and exit")
    parser.add_argument("--dry-run", action="store_true", help="show the transfers without making them")
    parser.add_argument("--built", default=root / "examples/catalog", type=Path, help="root the built catalogs live under")
    args = parser.parse_args()

    stems = manifest_stems(root)
    if not stems:
        raise SystemExit(f"no manifests found in {root / 'examples/manifests'}")
    if args.catalog and args.catalog not in stems:
        raise SystemExit(f"unknown catalog {args.catalog!r}, manifests are {stems}")
    selected = [args.catalog] if args.catalog else stems

    # --list feeds the build matrix, so a typo in the dispatch input fails here
    # rather than after a job has already spent ten minutes building.
    if args.list:
        print(json.dumps(selected))
        return 0

    leaf = ref_leaf(current_ref())
    rows = []
    for catalog in selected:
        tree = args.built / catalog
        root_json = tree / "catalog.json"
        if not root_json.is_file():
            raise SystemExit(
                f"{root_json} is missing, build it with "
                f"'uv run examples/tools/build.py --catalog {catalog}'"
            )
        catalog_id = json.loads(root_json.read_text())["id"]
        target, public_url = destination(catalog, leaf)
        count, size = tree_summary(tree)

        print(f"::group::{catalog} -> {target}")
        print(f"{count} files, {size / 1_048_576:.1f} MiB, catalog id {catalog_id}")
        sync(tree, target, args.dry_run)
        print("::endgroup::")

        if args.dry_run:
            print(f"dry run, nothing was uploaded to {target}")
        else:
            verify(public_url, catalog_id)
            rows.append((catalog, public_url, count, size))

    write_step_summary(rows)
    if rows:
        write_output("url", rows[-1][1])
    print(f"\n{len(rows)}/{len(selected)} catalogs published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
