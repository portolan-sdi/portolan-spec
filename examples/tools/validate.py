"""Validation, JSON schema plus the Portolan conformance rules tooling owns.

Checks every node against the committed schema, verifies each file:checksum is
a sha2-256 multihash, and fails on any self link.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import jsonschema

if TYPE_CHECKING:
    from reis.catalog import Node
    from reis.data import DataDefect
    from reis.data.reader import AssetReader, Locator


def _local_schema_validator(schema_path: Path) -> Callable[[dict], list[str]]:
    """A reis schema-pass validator bound to the working-copy schema.

    Reis's schema pass fetches the published profile schema. Here we point it at
    the committed schema under stac/ so the build tests the working copy, which
    is what the old validator did. Returns the jsonschema messages for one
    object, empty when it satisfies the schema.
    """
    schema = json.loads(schema_path.read_text())
    validator = jsonschema.Draft7Validator(schema)

    def validate_object(obj: dict) -> list[str]:
        return [error.message for error in validator.iter_errors(obj)]

    return validate_object


class _LocalOnlyReader:
    """An AssetReader that drops remote assets so the data pass reads only local
    files. Remote source assets, the live upstreams whose file:checksum is
    point-in-time, are skipped rather than fetched, keeping the build offline and
    free of false checksum mismatches."""

    def __init__(self, inner: "AssetReader") -> None:
        self._inner = inner

    def locate(self, node: "Node", href: str) -> "Locator | None":
        located = self._inner.locate(node, href)
        if located is None or located.is_remote:
            return None
        return located

    def stream(self, node: "Node", href: str):
        located = self._inner.locate(node, href)
        if located is None or located.is_remote:
            return None
        return self._inner.stream(node, href)


def _local_only_data_validator() -> "Callable[[Node, AssetReader], list[DataDefect]]":
    """Wrap reis's byte checker so it reads through a local-only reader."""
    from reis.data import checks

    def validate_node(node: "Node", reader: "AssetReader") -> "list[DataDefect]":
        return checks.check_node(node, _LocalOnlyReader(reader))

    return validate_node


def collection_findings(obj: dict) -> list[str]:
    """Return Portolan provenance findings the JSON schema delegates to tooling.

    Checks the two rules the schema leaves to the validator, that a collection
    has exactly one host provider and that it is the last element, and that a
    collection whose license is `other` carries a rel=license link."""
    out: list[str] = []
    provs = obj.get("providers", []) or []
    host_idx = [i for i, p in enumerate(provs) if "host" in (p.get("roles") or [])]
    if len(host_idx) != 1:
        out.append(f"providers must have exactly one host, found {len(host_idx)}")
    elif host_idx[0] != len(provs) - 1:
        out.append("host provider must be listed last")
    if obj.get("license") == "other":
        if not any(lk.get("rel") == "license" for lk in obj.get("links", []) or []):
            out.append("license is 'other' but no rel=license link is present")
    return out


def validate(out: Path, schema_path: Path) -> None:
    schema = json.loads(schema_path.read_text())
    validator = jsonschema.Draft7Validator(schema)
    errors = 0
    for jf in sorted(out.rglob("*.json")):
        obj = json.loads(jf.read_text())
        if obj.get("type") not in ("Catalog", "Collection", "Feature"):
            continue
        for e in validator.iter_errors(obj):
            errors += 1
            print(f"  SCHEMA {jf.relative_to(out)}: {e.message}", file=sys.stderr)
        # extra Portolan checks the schema delegates to tooling
        for a in obj.get("assets", {}).values():
            ck = a.get("file:checksum", "")
            if not re.fullmatch(r"1220[0-9a-f]{64}", ck):
                errors += 1
                print(f"  CHECKSUM {jf.relative_to(out)}: not a sha2-256 multihash: {ck}", file=sys.stderr)
        for lk in obj.get("links", []):
            if lk.get("rel") == "self":
                errors += 1
                print(f"  SELF-LINK {jf.relative_to(out)}", file=sys.stderr)
        if obj.get("type") == "Collection":
            for msg in collection_findings(obj):
                errors += 1
                print(f"  PROVENANCE {jf.relative_to(out)}: {msg}", file=sys.stderr)
    if errors:
        raise SystemExit(f"validation failed with {errors} error(s)")
    print(f"validation passed for {out}", file=sys.stderr)
