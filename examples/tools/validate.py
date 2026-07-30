"""Validate a built Portolan catalog with rashid, the canonical validator.

rashid defines Portolan conformance. This module is a thin adapter. It runs
rashid's metadata, structural, schema, and data passes over a built catalog,
feeds the schema pass the repo's working-copy schema under stac/, narrows the
data pass to local assets, and fails the build on any error finding.

The local-only reader used to live here. rashid now ships an equivalent
LocalOnlyReader and a data_reader_factory hook, added by portolan-sdi/rashid#87,
so the copy was deleted in favour of the upstream one. Same behaviour, one
implementation, and path resolution stays with the validator that defines it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
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


def validate(out: Path, schema_path: Path, baseline: dict | None = None) -> None:
    """Validate the built catalog at out with rashid and fail on any error.

    Runs the metadata pass (always), the STAC 1.1.0 structural pass, the schema
    pass against the working-copy schema, and the data pass narrowed to local
    assets. Every data rule still runs, a remote href is simply unfetchable, so
    a live upstream is never refetched during a build and a point-in-time
    checksum cannot produce a false mismatch.
    Prints every finding and raises SystemExit when rashid reports an error.

    When baseline is given, its accepted rules are filtered out first through
    check_catalogs.apply_baseline, the same logic the standalone gate uses, so
    a known non-conformance stays visible without failing the build.
    """
    from rashid import validate as rashid_validate
    from rashid.data.reader import LocalOnlyReader

    report = rashid_validate(
        out,
        structural=True,
        schema=True,
        schema_validator=_local_schema_validator(schema_path),
        data=True,
        data_reader_factory=LocalOnlyReader,
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
