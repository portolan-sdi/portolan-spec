# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.3", "awscli==1.46.3"]
# ///
"""Publish a built example catalog to the Portolan Mirrors organization on Source Cooperative.

examples/manifests/*.yaml each describe one whole catalog, and build.py turns a
manifest into a complete catalog tree under examples/catalog/<stem>/. This
uploads that tree to the portolan-mirrors/portolan-spec-examples product,
https://data.source.coop/portolan-mirrors/portolan-spec-examples/, so the
example is reachable at a real URL, which is the only way to exercise a Portolan
catalog the way a client actually reads one, over HTTP range requests.

The product holds only these example catalogs. The layout is
<catalog id>/<namespace>, where the namespace is `main` for main or master,
`branches/<slug>` for any other branch, and `PRs/<number>` for a pull request.
A PR number is stable across a force-push where a branch name is not, and it is
what the teardown deletes when the PR closes. The id comes from the manifest,
not the file name. Name each manifest after the id it declares, so
`portolan-reference.yaml` builds `catalog/portolan-reference/` and publishes to
`portolan-reference/`, one name everywhere.

Transfers run through the AWS CLI, pinned in the header above and run as
`python -m awscli`, so the client version is the one this script declares and
nothing has to be on PATH. `sync --delete` is scoped to one catalog's own
prefix, so a stale file from an earlier build is removed while everything else
published under portolan-mirrors/portolan-spec-examples/ is left alone.

The AWS CLI replaced s5cmd, which cannot work through the data proxy. Three
proxy behaviours decide it. The proxy forwards a plain PutObject to S3 on a
presigned URL that signs only the host, and S3 refused every s5cmd upload with
"There were headers present in the request which were not signed". The AWS CLI
sends PutObject as an aws-chunked upload instead, which the proxy re-signs with
its headers. The proxy's LIST returns keys relative to the account, so the
account has to be the bucket, and s5cmd then batch deletes under the account
alone, which the proxy cannot map. The AWS CLI deletes one object at a time.

The CLI finishes every transfer it can and then exits non-zero if any failed,
and this script then fails. After a sync it lists the prefix again and requires
the remote keys to equal the local files, so a stale file that survived or an
upload that went missing fails the run rather than passing quietly.

Every transfer goes through Source Cooperative's data proxy at
https://data.source.coop, with the credentials in the environment. In CI they
come from a GitHub OIDC sign-in as the service account
portolan-mirrors--spec-examples, so the repository stores no keys. The proxy
seals the credentials it issues, so they work against the proxy and nowhere
else.

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
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

# Source Cooperative's data proxy. It serves the public reads and it takes the
# writes as well. CI signs in at the proxy with a GitHub OIDC token, and the
# credentials it gets back are sealed to the proxy, so they are refused by
# s3.amazonaws.com. Every transfer therefore goes through the proxy.
PROXY = "https://data.source.coop"
# The Source Cooperative product, portolan-mirrors/portolan-spec-examples.
# data.source.coop resolves a path through the product record, so the product
# must exist for PUBLIC_BASE to serve what the upload writes.
ACCOUNT = "portolan-mirrors"
PRODUCT = "portolan-spec-examples"
# Through the proxy the account is the S3 bucket and the product is the first
# segment of every key. That is the only addressing the proxy's LIST answers
# consistently, since it returns account-relative keys even when the product is
# in the URL path. The AWS CLI uses path-style addressing for a custom endpoint,
# so a key lands at /<account>/<product>/<rest>, which the proxy maps.
S3_ENDPOINT = PROXY
BUCKET = ACCOUNT
# Set for every CLI call rather than left to the environment. With checksums on,
# the CLI sends each upload and part over HTTPS as aws-chunked with a checksum
# trailer, the one form the proxy re-signs whole. With them off it sends a
# plain body, which the proxy forwards on a host-only presigned URL that S3
# refuses. check_publish_proxy.py asserts the form on every upload.
CHECKSUM_CALCULATION = "when_supported"
# The same bytes over HTTPS. The proxy serves both, so the S3 URL path and the
# public URL path are identical.
PUBLIC_BASE = f"{PROXY}/{ACCOUNT}/{PRODUCT}"
# The two human-facing views of the same bytes. `data.` serves the objects,
# the bare domain serves Source Cooperative's file browser, and STAC Browser
# renders the catalog. All three are derived from PUBLIC_BASE in review_urls,
# never reassembled, so moving the repository moves all of them together.
SOURCE_COOP_BASE = f"https://source.coop/{ACCOUNT}/{PRODUCT}"
BROWSER_BASE = "https://browser.portolan-sdi.org/#/external/"

# The namespace taxonomy is main, branches/<slug>, and PRs/<number>.
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
    """Turn a git ref into one safe path segment, by lowercasing and collapsing unsafe runs to a dash."""
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
    what the published catalog calls itself.
    """
    if not catalog_id or "/" in catalog_id or ".." in catalog_id:
        raise SystemExit(f"refusing to publish catalog id {catalog_id!r}")
    tail = f"{catalog_id}/{ns}"
    return f"s3://{BUCKET}/{PRODUCT}/{tail}/", f"{PUBLIC_BASE}/{tail}/"


def key_prefix(target: str) -> str:
    """The S3 key prefix of an s3:// target, the part after the bucket."""
    head = f"s3://{BUCKET}/"
    if not target.startswith(head):
        raise SystemExit(f"target {target!r} is not in bucket {BUCKET!r}")
    return target.removeprefix(head)


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


def aws(*args: str) -> list[str]:
    """An AWS CLI command line pointed at the data proxy.

    The endpoint is passed on every call rather than through AWS_ENDPOINT_URL,
    so a stray environment cannot send these credentials anywhere else. The
    credentials come from the environment, AWS_ACCESS_KEY_ID,
    AWS_SECRET_ACCESS_KEY and AWS_SESSION_TOKEN, which the sign-in step in CI
    exports.
    """
    return [sys.executable, "-m", "awscli", "--endpoint-url", S3_ENDPOINT, *args]


def run(command: list[str], echo: bool = True) -> subprocess.CompletedProcess:
    """Run one CLI command, echoing it, and fail on any non-zero exit.

    The CLI exits 1 when any transfer failed and 2 when it skipped a file, and
    both are failures here. Nothing is half-published without the run going red.
    """
    print(f"$ {' '.join(command[1:])}", flush=True)
    env = {**os.environ, "AWS_REQUEST_CHECKSUM_CALCULATION": CHECKSUM_CALCULATION}
    completed = subprocess.run(
        command, capture_output=True, text=True, check=False, env=env
    )
    if echo:
        print(completed.stdout, end="")
    if completed.returncode != 0:
        print(completed.stderr, end="")
        raise SystemExit(f"aws exited {completed.returncode}: {' '.join(command[3:6])}")
    return completed


def remote_keys(prefix: str) -> set[str]:
    """Every key under `prefix`, relative to it, from a fresh listing.

    The listing is checked rather than trusted. A response that is not the
    shape the CLI documents, or a key outside the prefix that was asked for,
    means the proxy's addressing no longer matches this script, and every
    decision made from that listing would be wrong. Both fail here. An empty
    set means the listing returned no keys at all under the prefix.
    """
    completed = run(
        aws(
            "s3api", "list-objects-v2",
            "--bucket", BUCKET,
            "--prefix", prefix,
            "--output", "json",
        ),
        echo=False,
    )
    text = completed.stdout.strip()
    try:
        listing = json.loads(text) if text else {}
    except json.JSONDecodeError as exc:
        raise SystemExit(f"listing of {prefix!r} is not JSON, {exc}") from exc
    if not isinstance(listing, dict):
        raise SystemExit(f"listing of {prefix!r} is not an object, {listing!r}")
    echoed = listing.get("Prefix")
    if echoed not in (None, prefix):
        raise SystemExit(f"listing of {prefix!r} answered for prefix {echoed!r}")
    contents = listing.get("Contents") or []
    if not isinstance(contents, list):
        raise SystemExit(f"listing of {prefix!r} has malformed Contents")
    keys = set()
    for entry in contents:
        key = entry.get("Key") if isinstance(entry, dict) else None
        if not isinstance(key, str) or not key.startswith(prefix):
            raise SystemExit(
                f"listing of {prefix!r} returned key {key!r} outside the prefix, "
                "the proxy's key addressing has changed"
            )
        keys.add(key.removeprefix(prefix))
    return keys


def local_files(tree: Path) -> set[str]:
    """The relative paths of a built tree, as they will be published."""
    return {
        path.relative_to(tree).as_posix()
        for path in tree.rglob("*")
        if path.is_file() and path.name not in EXCLUDED_NAMES
    }


def sync(tree: Path, target: str, dry_run: bool) -> None:
    """Mirror one built catalog tree onto its own prefix, then prove it."""
    prefix = key_prefix(target)
    # `sync --delete` decides what to delete from the CLI's own listing, and
    # trusts it. Checking the same listing first means a proxy that changed its
    # key addressing fails here, before the CLI deletes keys it misread.
    remote_keys(prefix)
    # Scoped to this catalog's own prefix, so a file dropped from the manifest
    # disappears and nothing else in the bucket is touched.
    command = aws("s3", "sync", f"{tree}/", target, "--delete", "--no-progress")
    for name in sorted(EXCLUDED_NAMES):
        # A leading star, since the pattern is matched against the whole path.
        command += ["--exclude", f"*{name}"]
    if dry_run:
        command.append("--dryrun")
    run(command)
    if dry_run:
        return
    remote = remote_keys(prefix)
    local = local_files(tree)
    stale, missing = sorted(remote - local), sorted(local - remote)
    if stale or missing:
        raise SystemExit(
            f"{target} does not mirror {tree} after the sync, "
            f"{len(stale)} stale {stale[:5]}, {len(missing)} missing {missing[:5]}"
        )
    print(f"{target} holds exactly the {len(local)} built files")


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

    for catalog_id in catalog_ids:
        target, _ = destination(catalog_id, f"PRs/{number}")
        if f"/PRs/{number}/" not in target:
            raise SystemExit(f"refusing to tear down, unexpected target {target!r}")
        prefix = key_prefix(target)
        # A prefix with nothing under it is normal, a PR that never published.
        # It counts only when the listing itself is sound, remote_keys fails on
        # a malformed or mismatched one.
        before = remote_keys(prefix)
        if not before:
            print(f"nothing under {target}")
            continue
        command = aws("s3", "rm", target, "--recursive", "--only-show-errors")
        if dry_run:
            run(command + ["--dryrun"])
            print(f"dry run, {len(before)} objects would be deleted from {target}")
            continue
        run(command)
        left = remote_keys(prefix)
        if left:
            raise SystemExit(
                f"{len(left)} objects survived the teardown of {target}, "
                f"{sorted(left)[:5]}"
            )
        print(f"torn down {target}, {len(before)} objects")
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
