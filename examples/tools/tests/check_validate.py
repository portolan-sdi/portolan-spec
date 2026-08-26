# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "jsonschema>=4.26.0",
#   "rashid[data]>=0.1.7,<0.2.0",
# ]
# ///
"""Standalone checks for the rashid validation adapter.

Run:
    uv run examples/tools/tests/check_validate.py
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from validate import _local_schema_validator  # noqa: E402
from validate import _LocalOnlyReader  # noqa: E402

REPO = Path(__file__).resolve().parent.parent.parent.parent
SCHEMA = REPO / "stac/json-schema/v0.1.2/schema.json"
REFERENCE = REPO / "examples/catalog/portolan-reference"

import shutil  # noqa: E402
import tempfile  # noqa: E402

from validate import validate  # noqa: E402


def check_reference_catalog_passes() -> None:
    # Raises SystemExit if rashid reports any error finding.
    validate(REFERENCE, SCHEMA)


def check_self_link_fails() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "portolan-reference"
        shutil.copytree(REFERENCE, dst)
        # Inject a self link into one Collection. The v0.1.2 schema rejects
        # it. The specification no longer does, so the next schema version
        # drops this check and this test flips with it.
        col = dst / "boundaries/us-counties/collection.json"
        obj = json.loads(col.read_text())
        obj["links"].append({"rel": "self", "href": "collection.json"})
        col.write_text(json.dumps(obj))
        try:
            validate(dst, SCHEMA)
        except SystemExit:
            return
        raise AssertionError("a self link should fail validation")


def check_schema_validator_passes_conformant_root() -> None:
    validate_object = _local_schema_validator(SCHEMA)
    root = json.loads((REFERENCE / "catalog.json").read_text())
    assert validate_object(root) == [], validate_object(root)


def check_schema_validator_flags_broken_object() -> None:
    validate_object = _local_schema_validator(SCHEMA)
    root = json.loads((REFERENCE / "catalog.json").read_text())
    del root["type"]
    assert validate_object(root), "missing 'type' should be flagged"


class _FakeLocator:
    def __init__(self, is_remote: bool) -> None:
        self.is_remote = is_remote
        self.source = "x"


class _FakeReader:
    def __init__(self, remote: bool) -> None:
        self._remote = remote
        self.streamed = False

    def locate(self, node, href):
        return _FakeLocator(self._remote)

    def stream(self, node, href):
        self.streamed = True
        return iter([b"bytes"])


def check_local_only_reader_drops_remote() -> None:
    inner = _FakeReader(remote=True)
    reader = _LocalOnlyReader(inner)
    assert reader.locate(None, "https://example.invalid/a.parquet") is None
    assert reader.stream(None, "https://example.invalid/a.parquet") is None
    assert inner.streamed is False, "remote asset must not be streamed"


def check_local_only_reader_keeps_local() -> None:
    inner = _FakeReader(remote=False)
    reader = _LocalOnlyReader(inner)
    located = reader.locate(None, "a.parquet")
    assert located is not None and located.is_remote is False
    assert reader.stream(None, "a.parquet") is not None
    assert inner.streamed is True, "local asset must be streamed"


CHECKS = [
    check_schema_validator_passes_conformant_root,
    check_schema_validator_flags_broken_object,
    check_local_only_reader_drops_remote,
    check_local_only_reader_keeps_local,
    check_reference_catalog_passes,
    check_self_link_fails,
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
