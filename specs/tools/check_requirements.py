# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml>=6"]
# ///
"""Verify requirements.yaml and the spec prose agree, both directions.

The manifest (specs/portolan/requirements.yaml) assigns a stable ID to every
normative statement in the spec. Each entry anchors its ID to the exact
sentence it governs, so the check needs no markup inside the markdown:

1. Every manifest quote must appear verbatim (whitespace-normalized) in its
   spec file. Editing a normative sentence without updating the manifest
   fails here.
2. Every RFC 2119 keyword occurrence (MUST, MUST NOT, SHOULD, SHOULD NOT,
   MAY, REQUIRED, RECOMMENDED, OPTIONAL, uppercase) in a spec file must fall
   inside the span of some matched quote or exclusion. Adding a normative
   sentence without a manifest entry fails here.

3. The newest requirements census in CHANGELOG.md must match the manifest.
   The census is the "**Requirements manifest**: N requirements, now A MUST,
   B SHOULD, and C MAY." line a release writes. Nothing else reads the
   changelog, so before this check the census drifted every time a
   requirement landed without a release (#150).

Exclusions cover uppercase keyword mentions that are not requirements (for
example, prose explaining the RFC 2119 conventions themselves).

Downstream, the rashid validator vendors this manifest and enforces that every
MUST and SHOULD ID maps to at least one rule and one test.

Usage::

    uv run specs/tools/check_requirements.py
"""

from __future__ import annotations

import collections
import re
import sys
from pathlib import Path

import yaml

# specs/tools/check_requirements.py -> repo root is three levels up
ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST = ROOT / "specs" / "portolan" / "requirements.yaml"
CHANGELOG = ROOT / "CHANGELOG.md"

# The census line a release writes, matched against whitespace-normalized text
# because the changelog wraps it across two lines.
CENSUS = re.compile(
    r"\*\*Requirements manifest\*\*: (\d+) requirements, now (\d+) MUST, "
    r"(\d+) SHOULD, and (\d+) MAY\."
)

KEYWORD = re.compile(
    r"\b(MUST NOT|MUST|SHOULD NOT|SHOULD|MAY|REQUIRED|RECOMMENDED|OPTIONAL)\b"
)
SEVERITIES = {"MUST", "SHOULD", "MAY"}
ID_PATTERN = re.compile(r"^PORTO-(CORE|FMT)-\d{3}$")


def normalize(text: str) -> str:
    return " ".join(text.split())


def spans_of(needle: str, haystack: str) -> list[tuple[int, int]]:
    spans = []
    start = 0
    while (idx := haystack.find(needle, start)) != -1:
        spans.append((idx, idx + len(needle)))
        start = idx + 1
    return spans


def census_errors(manifest: dict) -> list[str]:
    """Compare the newest CHANGELOG.md census against the manifest.

    The topmost census line is the newest one, so a release that changes the
    requirement set and forgets to write a fresh census fails here rather than
    shipping a stale number. A changelog with no census line at all has nothing
    to drift.
    """
    matches = list(CENSUS.finditer(normalize(CHANGELOG.read_text())))
    if not matches:
        return []
    claimed = tuple(int(group) for group in matches[0].groups())
    counts = collections.Counter(e["severity"] for e in manifest["requirements"])
    actual = (
        len(manifest["requirements"]),
        counts["MUST"],
        counts["SHOULD"],
        counts["MAY"],
    )
    if claimed == actual:
        return []
    return [
        "CHANGELOG.md census reads {} requirements, {} MUST, {} SHOULD, {} MAY; "
        "the manifest holds {}, {}, {}, {}".format(*claimed, *actual)
    ]


def main() -> int:
    errors: list[str] = []
    manifest = yaml.safe_load(MANIFEST.read_text())
    errors.extend(census_errors(manifest))

    seen_ids: set[str] = set()
    per_file_spans: dict[str, list[tuple[int, int]]] = {}
    texts: dict[str, str] = {}

    for entry in manifest["requirements"]:
        rid, sev, rel, quote = (
            entry["id"],
            entry["severity"],
            entry["file"],
            normalize(entry["quote"]),
        )
        if not ID_PATTERN.match(rid):
            errors.append(f"{rid}: malformed ID")
        if rid in seen_ids:
            errors.append(f"{rid}: duplicate ID")
        seen_ids.add(rid)
        if sev not in SEVERITIES:
            errors.append(f"{rid}: severity {sev!r} not in {sorted(SEVERITIES)}")

        if rel not in texts:
            texts[rel] = normalize((ROOT / rel).read_text())
            per_file_spans[rel] = []
        found = spans_of(quote, texts[rel])
        if not found:
            errors.append(f"{rid}: quote not found verbatim in {rel}")
        per_file_spans[rel].extend(found)

    for entry in manifest.get("exclusions", []):
        rel, quote = entry["file"], normalize(entry["quote"])
        if rel not in texts:
            texts[rel] = normalize((ROOT / rel).read_text())
            per_file_spans[rel] = []
        found = spans_of(quote, texts[rel])
        if not found:
            errors.append(f"exclusion quote not found verbatim in {rel}: {quote[:60]}...")
        per_file_spans[rel].extend(found)

    for rel in manifest["files"]:
        if rel not in texts:
            texts[rel] = normalize((ROOT / rel).read_text())
            per_file_spans[rel] = []
        spans = per_file_spans[rel]
        for match in KEYWORD.finditer(texts[rel]):
            if not any(lo <= match.start() and match.end() <= hi for lo, hi in spans):
                context = texts[rel][max(0, match.start() - 60) : match.end() + 60]
                errors.append(
                    f"{rel}: keyword {match.group()!r} outside any manifest "
                    f"quote or exclusion: ...{context}..."
                )

    if errors:
        print(f"{len(errors)} requirement-manifest error(s):\n")
        for err in errors:
            print(f"  - {err}")
        return 1

    count = len(manifest["requirements"])
    print(f"OK: {count} requirements anchored; all keyword occurrences covered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
