"""Validate a built Portolan catalog with rashid, the canonical validator.

rashid defines Portolan conformance. This module is a thin adapter. It runs
rashid's metadata, structural, schema, and data passes over a built catalog,
feeds the schema pass the repo's working-copy schema under stac/, restricts the
data pass to local assets, and fails the build on any error finding.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from rashid.catalog import Node
    from rashid.data import DataDefect
    from rashid.data.reader import AssetReader, Locator
    from rashid.schema import Validator


def _local_schema_validator(schema_path: Path) -> "Validator":
    """A rashid schema-pass validator bound to the working-copy schema.

    Rashid's schema pass resolves the published profile schema from the copies
    bundled in its wheel. Here we point it at the committed schema under stac/
    so the build tests the working copy. rashid's own `validator_from_schema`
    builds it, which keeps the SchemaError contract and the oneOf error
    narrowing rashid's reporting expects. Returns the schema errors for one
    object, empty when it satisfies the schema.
    """
    from rashid.schema import validator_from_schema

    return validator_from_schema(json.loads(schema_path.read_text()))


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
    """Wrap rashid's byte checker so it reads through a local-only reader."""
    from rashid.data import checks

    def validate_node(node: "Node", reader: "AssetReader") -> "list[DataDefect]":
        return checks.check_node(node, _LocalOnlyReader(reader))

    return validate_node


def validate(out: Path, schema_path: Path, baseline: dict | None = None) -> None:
    """Validate the built catalog at out with rashid and fail on any error.

    Runs the metadata pass (always), the STAC 1.1.0 structural pass, the schema
    pass against the working-copy schema, and the data pass over local assets.
    Prints every finding and raises SystemExit when rashid reports an error.

    When baseline is given, its accepted rules are filtered out first through
    check_catalogs.apply_baseline, the same logic the standalone gate uses, so
    a known non-conformance stays visible without failing the build.
    """
    from rashid import validate as rashid_validate

    report = rashid_validate(
        out,
        structural=True,
        schema=True,
        schema_validator=_local_schema_validator(schema_path),
        data=True,
        data_validator=_local_only_data_validator(),
    )
    for finding in report.findings:
        print(
            f"  {finding.rule_id} {finding.severity.value} {finding.path}: {finding.message}",
            file=sys.stderr,
        )
    if baseline:
        from check_catalogs import apply_baseline

        data = {
            "findings": [
                {
                    "rule_id": finding.rule_id,
                    "severity": finding.severity.value,
                    "path": finding.path,
                    "message": finding.message,
                }
                for finding in report.findings
            ]
        }
        _, reasons = apply_baseline(data, baseline)
        if reasons:
            for reason in reasons:
                print(f"  UNEXPECTED {reason}", file=sys.stderr)
            raise SystemExit(f"validation failed, {len(reasons)} reason(s) above")
        print(f"validation passed for {out}, baseline accepted the rest", file=sys.stderr)
        return
    if not report.passed:
        errors = sum(1 for f in report.findings if f.severity.value == "error")
        raise SystemExit(f"validation failed with {errors} error(s)")
    print(f"validation passed for {out}", file=sys.stderr)
