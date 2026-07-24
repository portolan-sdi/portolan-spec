# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "jsonschema>=4.26.0",
#   "reis[data] @ git+https://github.com/portolan-sdi/reis.git@45207def50768cdb03eaa28f02215fabfdacacda",
# ]
# ///
"""Standalone checks for the reis validation adapter.

Run:
    uv run examples/tools/tests/check_validate.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from validate import _local_schema_validator  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent.parent
SCHEMA = REPO / "stac/json-schema/v0.1.0/schema.json"
REFERENCE = REPO / "examples/catalog/reference"


def check_schema_validator_passes_conformant_root() -> None:
    validate_object = _local_schema_validator(SCHEMA)
    root = json.loads((REFERENCE / "catalog.json").read_text())
    assert validate_object(root) == [], validate_object(root)


def check_schema_validator_flags_broken_object() -> None:
    validate_object = _local_schema_validator(SCHEMA)
    root = json.loads((REFERENCE / "catalog.json").read_text())
    del root["type"]
    assert validate_object(root), "missing 'type' should be flagged"


CHECKS = [
    check_schema_validator_passes_conformant_root,
    check_schema_validator_flags_broken_object,
]


def main() -> int:
    failed = 0
    for check in CHECKS:
        try:
            check()
            print(f"PASS {check.__name__}")
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {check.__name__}: {exc}")
    if failed:
        print(f"{failed} check(s) failed")
        return 1
    print("all validate checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
