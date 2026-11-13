# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6.0.3"]
# ///
"""Standalone check for publish_catalogs.py's URL derivation.

The S3 target and the public URL address the same bytes, so they must name the
same product and the same `<catalog id>/<namespace>` tail. The review links
derive from the public URL and must stay under the same product. This asserts
those relations offline, with no network and no credentials.

Run: uv run examples/tools/tests/check_publish_urls.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import publish_catalogs as pc  # noqa: E402

PRODUCT = "portolan-mirrors/portolan-spec-examples"


def main() -> int:
    failures = []

    def expect(label, got, want):
        if got != want:
            failures.append(f"{label}: got {got!r}, want {want!r}")

    s3, public = pc.destination("portolan-reference", "main")
    expect("s3", s3, f"s3://us-west-2.opendata.source.coop/{PRODUCT}/portolan-reference/main/")
    expect("public", public, f"https://data.source.coop/{PRODUCT}/portolan-reference/main/")

    s3, public = pc.destination("portolan-reference", "PRs/248")
    expect("pr s3", s3, f"s3://us-west-2.opendata.source.coop/{PRODUCT}/portolan-reference/PRs/248/")
    expect("pr public", public, f"https://data.source.coop/{PRODUCT}/portolan-reference/PRs/248/")

    browser, files = pc.review_urls(public)
    expect(
        "browser",
        browser,
        "https://browser.portolan-sdi.org/#/external/"
        f"data.source.coop/{PRODUCT}/portolan-reference/PRs/248/catalog.json",
    )
    expect("files", files, f"https://source.coop/{PRODUCT}/portolan-reference/PRs/248")

    # The old product must not be derivable any more.
    try:
        pc.review_urls("https://data.source.coop/portolan/portolan-pipeline/x/main/")
    except SystemExit:
        pass
    else:
        failures.append("review_urls accepted a URL outside the current product")

    for bad in ("", "a/b", ".."):
        try:
            pc.destination(bad, "main")
        except SystemExit:
            continue
        failures.append(f"destination accepted catalog id {bad!r}")

    for line in failures:
        print(f"FAIL {line}", file=sys.stderr)
    if not failures:
        print("publish URL derivation ok")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
