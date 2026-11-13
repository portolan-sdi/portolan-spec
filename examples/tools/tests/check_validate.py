# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "jsonschema>=4.26.0",
#   "rashid[data]>=0.1.8,<0.2.0",
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
SCHEMA = REPO / "stac/json-schema/schema.json"
REFERENCE = REPO / "examples/catalog/portolan-reference"

import shutil  # noqa: E402
import tempfile  # noqa: E402

from validate import validate  # noqa: E402


def check_reference_catalog_passes() -> None:
    # Raises SystemExit if rashid reports any error finding.
    validate(REFERENCE, SCHEMA)


def check_self_link_passes() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        dst = Path(tmp) / "portolan-reference"
        shutil.copytree(REFERENCE, dst)
        # Inject a self link into one Collection. The schemas through v0.1.2
        # reject it. PORTO-CORE-034 is retired, so v0.2.0 accepts it.
        col = dst / "boundaries/us-counties/collection.json"
        obj = json.loads(col.read_text())
        obj["links"].append(
            {
                "rel": "self",
                "href": "https://example.org/us-counties/collection.json",
                "type": "application/json",
            }
        )
        col.write_text(json.dumps(obj))
        try:
            validate(dst, SCHEMA)
        except SystemExit as exc:
            raise AssertionError("a self link should pass validation") from exc


def check_absolute_structural_href_passes() -> None:
    # PORTO-CORE-034 also required a relative structural href. v0.2.0 drops
    # that rule, so an absolute child href passes the schema.
    obj = json.loads((REFERENCE / "boundaries/catalog.json").read_text())
    for link in obj["links"]:
        if link["rel"] == "child":
            link["href"] = "https://example.org/boundaries/" + link["href"].removeprefix("./")
    validate_object = _local_schema_validator(SCHEMA)
    assert validate_object(obj) == [], validate_object(obj)


def check_schema_validator_passes_conformant_root() -> None:
    validate_object = _local_schema_validator(SCHEMA)
    root = json.loads((REFERENCE / "catalog.json").read_text())
    assert validate_object(root) == [], validate_object(root)


def check_schema_validator_flags_broken_object() -> None:
    validate_object = _local_schema_validator(SCHEMA)
    root = json.loads((REFERENCE / "catalog.json").read_text())
    del root["type"]
    assert validate_object(root), "missing 'type' should be flagged"


# Each rule that the schema gained after v0.2.0 gets one check that a
# conforming object passes and one check that a broken object is flagged.
# The objects come from the reference catalog and the stac/ examples.
VECTOR = REFERENCE / "boundaries/us-counties/collection.json"
RASTER = REFERENCE / "raster/sample-cog/collection.json"
PARTITIONED = REPO / "stac/examples/vector-partitioned-collection.json"
ITEM = REPO / "stac/examples/vector-partitioned-item.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _errors(obj: dict) -> list:
    return _local_schema_validator(SCHEMA)(obj)


def _with_data_href(href: str, **fields) -> dict:
    obj = _load(VECTOR)
    obj["assets"]["data"]["href"] = href
    obj["assets"]["data"].update(fields)
    return obj


def check_s3_href_with_https_alternate_passes() -> None:
    # PORTO-CORE-087: an s3 href conforms if alternate has an https URL.
    obj = _with_data_href(
        "s3://example-bucket/us-counties.parquet",
        alternate={
            "https": {"href": "https://example.org/us-counties.parquet"}
        },
    )
    assert _errors(obj) == [], _errors(obj)


def check_s3_href_without_https_alternate_flagged() -> None:
    bare = _with_data_href("s3://example-bucket/us-counties.parquet")
    assert _errors(bare), "an s3 href with no alternate should be flagged"
    s3_only = _with_data_href(
        "s3://example-bucket/us-counties.parquet",
        alternate={"s3": {"href": "s3://other-bucket/us-counties.parquet"}},
    )
    assert _errors(s3_only), "an alternate with no https href should be flagged"
    http = _with_data_href("http://example.org/us-counties.parquet")
    assert _errors(http), "an http href with no alternate should be flagged"


def check_partition_glob_bucket_url_passes() -> None:
    # PORTO-FMT-064: clients list files to expand the glob.
    obj = _load(PARTITIONED)
    assert obj["partition:glob"].startswith("s3://")
    assert _errors(obj) == [], _errors(obj)
    obj["partition:glob"] = "gs://example-bucket/buildings/*/*.parquet"
    assert _errors(obj) == [], _errors(obj)


def check_partition_glob_unlistable_flagged() -> None:
    for glob in (
        "https://data.example.org/buildings/*/*.parquet",
        "HTTP://data.example.org/buildings/*/*.parquet",
        "./buildings/*/*.parquet",
    ):
        obj = _load(PARTITIONED)
        obj["partition:glob"] = glob
        assert _errors(obj), f"partition:glob {glob!r} should be flagged"


def check_data_href_single_file_passes() -> None:
    # PORTO-FMT-065: a query string and an IPv6 host are not globs.
    for href in (
        "./us-counties.parquet?version=2",
        "https://[2001:db8::1]:8443/us-counties.parquet",
    ):
        obj = _with_data_href(href)
        assert _errors(obj) == [], (href, _errors(obj))


def check_data_href_glob_flagged() -> None:
    for href in (
        "./*.parquet",
        "./part-[0-9].parquet",
        "https://[2001:db8::1]/part-[0-9].parquet",
    ):
        obj = _with_data_href(href)
        assert _errors(obj), f"data href {href!r} should be flagged"


def check_pmtiles_without_visual_flagged() -> None:
    # PORTO-FMT-062: a PMTiles asset has the visual role.
    obj = _load(VECTOR)
    pmtiles = [
        a for a in obj["assets"].values()
        if a["type"] == "application/vnd.pmtiles"
    ]
    assert pmtiles and all("visual" in a["roles"] for a in pmtiles)
    assert _errors(obj) == [], _errors(obj)
    pmtiles[0]["roles"] = ["data"]
    assert _errors(obj), "a PMTiles asset without visual should be flagged"


def check_item_without_data_asset_flagged() -> None:
    # PORTO-CORE-083: every item carries an asset with the data role.
    item = _load(ITEM)
    assert _errors(item) == [], _errors(item)
    for asset in item["assets"].values():
        asset["roles"] = ["metadata"]
    assert _errors(item), "an item with no data asset should be flagged"


def _classes(*titles: str) -> list[dict]:
    return [
        {"value": i + 1, "name": f"class-{i + 1}", "title": title}
        for i, title in enumerate(titles)
    ]


def check_band_classes_pass() -> None:
    # PORTO-FMT-050 and PORTO-FMT-052. The sample COG has three bands, so
    # a class list sits on its band.
    obj = _load(RASTER)
    data = obj["assets"]["data"]
    assert len(data["bands"]) > 1
    data["bands"][0]["classification:classes"] = _classes("Water", "Land")
    assert _errors(obj) == [], _errors(obj)
    # A single-band raster has its class list on the asset.
    data["bands"] = data["bands"][:1]
    del data["bands"][0]["classification:classes"]
    data["classification:classes"] = _classes("Water", "Land")
    assert _errors(obj) == [], _errors(obj)


def check_misplaced_or_untitled_classes_flagged() -> None:
    multiband = _load(RASTER)
    multiband["assets"]["data"]["classification:classes"] = _classes("Water")
    assert _errors(multiband), "classes on a multiband asset should be flagged"

    single = _load(RASTER)
    data = single["assets"]["data"]
    data["bands"] = data["bands"][:1]
    data["bands"][0]["classification:classes"] = _classes("Water")
    assert _errors(single), "classes on the band of one band should be flagged"

    untitled = _load(RASTER)
    band = untitled["assets"]["data"]["bands"][0]
    band["classification:classes"] = _classes("Water")
    del band["classification:classes"][0]["title"]
    assert _errors(untitled), "a class with no title should be flagged"


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
    check_self_link_passes,
    check_absolute_structural_href_passes,
    check_s3_href_with_https_alternate_passes,
    check_s3_href_without_https_alternate_flagged,
    check_partition_glob_bucket_url_passes,
    check_partition_glob_unlistable_flagged,
    check_data_href_single_file_passes,
    check_data_href_glob_flagged,
    check_pmtiles_without_visual_flagged,
    check_item_without_data_asset_flagged,
    check_band_classes_pass,
    check_misplaced_or_untitled_classes_flagged,
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
