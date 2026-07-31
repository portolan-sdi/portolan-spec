# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.3"]
# ///
"""Publish a built example catalog to the Portolan repository on Source Cooperative.

examples/manifests/*.yaml each describe one whole catalog, and build.py turns a
manifest into a complete catalog tree under examples/catalog/<stem>/. This
uploads that tree to https://data.source.coop/portolan/portolan-pipeline/ so the
example is reachable at a real URL, which is the only way to exercise a Portolan
catalog the way a client actually reads one, over HTTP range requests.

portolan-pipeline already publishes into this same repository, so the prefix
taxonomy here is its taxonomy rather than a second one. The layout is
<catalog id>/<namespace>, where the namespace is `main` for main or master,
`branches/<slug>` for any other branch, and `PRs/<number>` for a pull request.
A PR number is stable across a force-push where a branch name is not, and it is
what the teardown deletes when the PR closes. The id comes from the manifest,
not the file name. Name each manifest after the id it declares, so
`portolan-reference.yaml` builds `catalog/portolan-reference/` and publishes to
`portolan-reference/`, one name everywhere.

Transfers run through s5cmd rather than the AWS CLI. A catalog is a few hundred
small JSON files next to a handful of large Parquet and COG assets, and s5cmd
saturates that shape far better. `sync --delete` is scoped to one catalog's own
prefix, so a stale file from an earlier build is removed while everything else
published under portolan/portolan-pipeline/ is left alone.

After the upload it refetches the published catalog.json over HTTPS and checks
that it parses and still carries the id that was uploaded. A sync that reported
success but published nothing readable is the failure worth catching.

Usage::

    uv run examples/tools/publish_catalogs.py --list
    uv run examples/tools/publish_catalogs.py --catalog portolan-reference --dry-run
    uv run examples/tools/publish_catalogs.py --catalog portolan-reference
    uv run examples/tools/publish_catalogs.py --teardown-pr 106 --dry-run
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

import yaml

BUCKET = "s3://us-west-2.opendata.source.coop"
# The Source Cooperative repository. Both halves of this pair have to move
# together, they address the same bytes over S3 and over HTTPS.
REPO_PREFIX = "portolan/portolan-pipeline"
PUBLIC_BASE = "https://data.source.coop/portolan/portolan-pipeline"
# The two human-facing views of the same bytes. `data.` serves the objects,
# the bare domain serves Source Cooperative's file browser, and STAC Browser
# renders the catalog. All three are derived from PUBLIC_BASE in review_urls,
# never reassembled, so moving the repository moves all of them together.
SOURCE_COOP_BASE = "https://source.coop/portolan/portolan-pipeline"
BROWSER_BASE = "https://browser.portolan-sdi.org/#/external/"

# portolan-pipeline publishes into this same repository, so its prefix taxonomy
# is the one to match rather than invent a second. See its docs/branch-versioning.md.
DEFAULT_BRANCHES = {"main", "master"}
# Everything outside this set collapses to a single dash, so a branch name is
# one path segment. `feat/x` becomes `feat-x`, never a nested directory.
UNSAFE_IN_SLUG = re.compile(r"[^a-z0-9._-]+")
# Cloudflare fronts data.source.coop and 403s the default Python-urllib agent.
USER_AGENT = "portolan-spec-publish (+https://github.com/portolan-sdi/portolan-spec)"
# Finder litters the tree on macOS. It is gitignored, so CI never sees it, but a
# maintainer publishing from a working copy would otherwise ship it.
EXCLUDED_NAMES = {".DS_Store"}


def _repo_root() -> Path:
    # examples/tools/publish_catalogs.py -> repo root is three levels up
    return Path(__file__).resolve().parent.parent.parent


def manifest_catalogs(root: Path) -> dict[str, str]:
    """Every catalog this repo can build, mapping manifest stem to catalog id.

    The stem names the build directory and the matrix entry, the id names the
    published prefix. Every manifest is named after the id it declares, so by
    convention the two coincide. This still reads the declared id rather than
    assuming it from the stem, because the id is what a catalog is published
    under and a manifest that breaks the convention has to be caught, not
    silently published to a prefix nobody named.
    """
    manifests = root / "examples/manifests"
    if not manifests.is_dir():
        return {}
    found = {}
    for path in sorted(manifests.iterdir()):
        if path.suffix not in {".yaml", ".yml"}:
            continue
        declared = yaml.safe_load(path.read_text()).get("id")
        if not declared:
            raise SystemExit(f"{path} declares no id, which names its published prefix")
        found[path.stem] = str(declared)
    return found


def slugify_ref(ref: str) -> str:
    """Turn a git ref into one safe path segment, as portolan-pipeline does."""
    slug = UNSAFE_IN_SLUG.sub("-", ref.strip().lower()).strip("-./")
    return slug or "unnamed"


def _git_branch(command: list[str]) -> str:
    """Stripped stdout of a git branch-name command, empty when it fails."""
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, check=True, timeout=10
        )
    except (subprocess.SubprocessError, OSError):
        return ""
    return completed.stdout.strip()


def local_branch() -> str:
    """The checked-out branch, for a run with no CI environment."""
    branch = _git_branch(["git", "branch", "--show-current"])
    if branch:
        return branch
    branch = _git_branch(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if branch and branch != "HEAD":
        return branch
    return "local"


def pull_request_number() -> str | None:
    """The PR this run belongs to, when it is a pull_request event."""
    if os.environ.get("GITHUB_EVENT_NAME") != "pull_request":
        return None
    # refs/pull/123/merge. The trailing slash is required, matching upstream.
    match = re.search(r"refs/pull/(\d+)/", os.environ.get("GITHUB_REF", ""))
    number = match.group(1) if match else os.environ.get("PR_NUMBER", "")
    if not number.isdigit():
        # Upstream falls back to a literal "0" here. Publishing every
        # unidentifiable run on top of PRs/0 is worse than refusing.
        raise SystemExit(
            "pull_request event with no usable PR number, "
            f"GITHUB_REF={os.environ.get('GITHUB_REF', '')!r}"
        )
    return number


def namespace() -> str:
    """The per-run prefix segment, keyed on the git context.

    A pull request goes to PRs/<number>, stable across a force-push where a
    branch name is not, and deletable by number when the PR closes.

    The default-branch test is on the raw ref, not a lowercased one, matching
    upstream. It reads like an oversight and is the safer behaviour, a branch
    named `Main` lands in branches/ rather than overwriting the canonical
    catalog at main/.
    """
    pr = pull_request_number()
    if pr:
        return f"PRs/{pr}"
    event = os.environ.get("GITHUB_EVENT_NAME")
    if event in {"push", "workflow_dispatch"}:
        ref = os.environ.get("GITHUB_REF_NAME") or local_branch()
    else:
        ref = local_branch()
    if ref in DEFAULT_BRANCHES:
        return "main"
    return f"branches/{slugify_ref(ref)}"


def destination(catalog_id: str, ns: str) -> tuple[str, str]:
    """The s3:// target and the public https:// URL for one catalog and run.

    Keyed on the catalog id rather than the manifest file name, since the id is
    what the published catalog calls itself and what portolan-pipeline keys on.
    """
    if not catalog_id or "/" in catalog_id or ".." in catalog_id:
        raise SystemExit(f"refusing to publish catalog id {catalog_id!r}")
    tail = f"{REPO_PREFIX}/{catalog_id}/{ns}"
    return f"{BUCKET}/{tail}/", f"{PUBLIC_BASE}/{catalog_id}/{ns}/"


def review_urls(public_url: str) -> tuple[str, str]:
    """The STAC Browser and Source Cooperative views of a published catalog.

    Both are derived from the public URL rather than reassembled from the parts,
    so a prefix that publishes to one place cannot link to another. STAC Browser
    addresses an external catalog by URL with the scheme dropped, and the file
    browser serves the same path from the bare domain.
    """
    if not public_url.startswith(PUBLIC_BASE):
        raise SystemExit(f"cannot derive review links from {public_url!r}")
    browser = f"{BROWSER_BASE}{public_url.removeprefix('https://')}catalog.json"
    tail = public_url.removeprefix(PUBLIC_BASE).rstrip("/")
    return browser, f"{SOURCE_COOP_BASE}{tail}"


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
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise SystemExit(f"s5cmd failed with exit {completed.returncode}, {target}")


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


def teardown(catalog_ids: list[str], number: str, dry_run: bool) -> int:
    """Delete one pull request's preview prefixes.

    Guarded in layers, because this is the only code here that deletes a prefix
    outright rather than reconciling one. The number must be all digits, and the
    resolved target must still look like a PR prefix after it is built. Neither
    main/ nor branches/ can be reached even if a caller lies about the number.
    """
    if not number.isdigit():
        raise SystemExit(f"refusing to tear down, PR number is not numeric, {number!r}")
    if shutil.which("s5cmd") is None:
        raise SystemExit("s5cmd is not on PATH, see https://github.com/peak/s5cmd")

    for catalog_id in catalog_ids:
        target, _ = destination(catalog_id, f"PRs/{number}")
        if f"/PRs/{number}/" not in target:
            raise SystemExit(f"refusing to tear down, unexpected target {target!r}")
        command = ["s5cmd"]
        if dry_run:
            command.append("--dry-run")
        # A prefix with nothing under it is normal, a PR that never published.
        command += ["rm", f"{target}*"]
        print(f"$ {' '.join(command)}")
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        print(completed.stdout, end="")
        if completed.returncode != 0 and "no object found" not in completed.stderr:
            raise SystemExit(completed.stderr.strip())
        print(f"torn down {target}")
    return 0


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
    parser.add_argument("--teardown-pr", default=None, metavar="N", help="delete the PRs/N preview of every catalog and exit")
    args = parser.parse_args()

    catalogs = manifest_catalogs(root)
    if not catalogs:
        raise SystemExit(f"no manifests found in {root / 'examples/manifests'}")
    if args.catalog and args.catalog not in catalogs:
        raise SystemExit(
            f"unknown catalog {args.catalog!r}, manifests are {sorted(catalogs)}"
        )
    selected = [args.catalog] if args.catalog else sorted(catalogs)

    # --list feeds the build matrix, so a typo in the dispatch input fails here
    # rather than after a job has already spent ten minutes building.
    if args.list:
        print(json.dumps(selected))
        return 0

    # Identity, not truthiness. An empty --teardown-pr is a caller that meant to
    # tear down and lost the number, and falling through to publish there would
    # upload where it was asked to delete.
    if args.teardown_pr is not None:
        return teardown(
            [catalogs[stem] for stem in selected], args.teardown_pr, args.dry_run
        )

    ns = namespace()
    rows = []
    for stem in selected:
        tree = args.built / stem
        root_json = tree / "catalog.json"
        if not root_json.is_file():
            raise SystemExit(
                f"{root_json} is missing, build it with "
                f"'uv run examples/tools/build.py --catalog {stem}'"
            )
        # The manifest names the prefix, the build has to agree. A rebuild that
        # changed the id while the manifest did not would otherwise publish to
        # one prefix and be verified at another.
        built_id = json.loads(root_json.read_text())["id"]
        if built_id != catalogs[stem]:
            raise SystemExit(
                f"{root_json} has id {built_id!r} but its manifest declares "
                f"{catalogs[stem]!r}, rebuild before publishing"
            )
        target, public_url = destination(built_id, ns)
        count, size = tree_summary(tree)

        print(f"::group::{stem} -> {target}")
        print(f"{count} files, {size / 1_048_576:.1f} MiB, catalog id {built_id}")
        sync(tree, target, args.dry_run)
        print("::endgroup::")

        if args.dry_run:
            print(f"dry run, nothing was uploaded to {target}")
        else:
            verify(public_url, built_id)
            rows.append((built_id, public_url, count, size))

    write_step_summary(rows)
    if rows:
        # The matrix publishes one catalog per job, so the last row is the only
        # row under CI. These feed the pull request comment and the environment
        # URL, and a dry run writes none of them, which is what keeps the
        # comment step from firing on a run that uploaded nothing.
        catalog_id, public_url, count, size = rows[-1]
        browser_url, repo_url = review_urls(public_url)
        write_output("url", public_url)
        write_output("browser_url", browser_url)
        write_output("repo_url", repo_url)
        write_output("files", str(count))
        write_output("size", f"{size / 1_048_576:.1f} MiB")
        print(f"browse {browser_url}")
        print(f"files  {repo_url}")
    print(f"\n{len(rows)}/{len(selected)} catalogs published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
