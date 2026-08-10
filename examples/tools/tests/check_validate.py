# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "jsonschema>=4.26.0",
#   # Kept in step with build.py's pin by hand, this script runs standalone.
#   "rashid[data] @ git+https://github.com/portolan-sdi/rashid@56fd275a5286372f4483a4c85c60ec4ed3d745d8",
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

REPO = Path(__file__).resolve().parent.parent.parent.parent
SCHEMA = REPO / "stac/json-schema/v0.1.0/schema.json"
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
        # Inject a forbidden self link into one Collection.
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


def _reader_over(inner):
    """rashid's LocalOnlyReader wrapped around a fake inner reader.

    Its real constructor takes a CatalogGraph and builds a FilesystemHttpReader
    itself, so there is no injection point. This bypasses __init__ and sets the
    private attribute instead. That is a deliberate dependency on an upstream
    internal, and the cost of having deleted our own copy of this class. If
    rashid renames `_inner` this fails loudly here rather than silently widening
    the data pass, which is the failure that would actually matter.
    """
    from rashid.data.reader import LocalOnlyReader

    # Decision, 2026-07-30. The two callers below were written against this repo's
    # own _LocalOnlyReader, which this branch deleted in favour of rashid's. They
    # are kept rather than deleted, as an upstream contract test. The reason is
    # that check_validate_narrows_the_data_pass_to_local_assets proves the factory
    # is handed to rashid and proves nothing about what the factory does, so if
    # LocalOnlyReader ever stopped dropping remote hrefs the wiring check would
    # still pass and naip-mosaic's build would quietly start streaming 1.86 TB.
    # These two are the only thing asserting that behaviour, and the private
    # attribute below is the price of asserting it.
    reader = LocalOnlyReader.__new__(LocalOnlyReader)
    reader._inner = inner
    return reader


def check_local_only_reader_drops_remote() -> None:
    inner = _FakeReader(remote=True)
    reader = _reader_over(inner)
    assert reader.locate(None, "https://example.invalid/a.parquet") is None
    assert reader.stream(None, "https://example.invalid/a.parquet") is None
    assert inner.streamed is False, "remote asset must not be streamed"


def check_local_only_reader_keeps_local() -> None:
    inner = _FakeReader(remote=False)
    reader = _reader_over(inner)
    located = reader.locate(None, "a.parquet")
    assert located is not None and located.is_remote is False
    assert reader.stream(None, "a.parquet") is not None
    assert inner.streamed is True, "local asset must be streamed"


def check_validate_narrows_the_data_pass_to_local_assets() -> None:
    """The adapter must hand rashid the local-only factory.

    If this wiring is ever dropped the build silently starts streaming every
    remote asset, which for naip-mosaic is 1.86 TB. Nothing else catches that,
    so assert the argument rather than trusting the call site to stay put.
    """
    import rashid
    from rashid.data.reader import LocalOnlyReader

    captured: dict = {}
    real = rashid.validate

    def spy(*args, **kwargs):
        captured.update(kwargs)
        return real(*args, **kwargs)

    rashid.validate = spy
    try:
        validate(REFERENCE, SCHEMA)
    finally:
        rashid.validate = real
    assert captured.get("data_reader_factory") is LocalOnlyReader, captured.get(
        "data_reader_factory")


CHECKS = [
    check_schema_validator_passes_conformant_root,
    check_schema_validator_flags_broken_object,
    check_local_only_reader_drops_remote,
    check_local_only_reader_keeps_local,
    check_validate_narrows_the_data_pass_to_local_assets,
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
