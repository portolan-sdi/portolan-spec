# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.3",
#   "duckdb>=1.5.4",
#   "pyarrow>=24",
#   "geoparquet-io @ git+https://github.com/yharby/geoparquet-io.git@f27e53108910f19bd74a9ff4be5c7d97b104753c",
# ]
# ///
"""Standalone compliance checks for build.py's pure helpers.

Imports helpers directly from build.py and asserts the Portolan conformance
rules the JSON schema delegates to tooling. Run:
    uv run examples/tests/check_compliance.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import build  # noqa: E402

HOST = {"name": "Portolan SDI", "url": "https://github.com/portolan-sdi",
        "email": "portolan@googlegroups.com"}


def check_official_host_moved_last() -> None:
    spec = {"id": "x/y", "license": "CC0-1.0", "providers": [
        {"name": "H", "roles": ["producer", "host"], "url": "https://h"},
        {"name": "P", "roles": ["processor"]},
    ]}
    providers, is_mirror = build.resolve_providers(spec, HOST)
    assert is_mirror is False, "producer-host collection is official"
    assert providers[-1]["name"] == "H", f"host not last: {providers}"


def check_multiple_hosts_error() -> None:
    spec = {"id": "x/y", "license": "CC0-1.0", "providers": [
        {"name": "H1", "roles": ["host"], "url": "https://h1"},
        {"name": "H2", "roles": ["producer", "host"], "url": "https://h2"},
    ]}
    try:
        build.resolve_providers(spec, HOST)
    except ValueError:
        return
    raise AssertionError("two host providers did not raise ValueError")


def check_mirror_appends_host_last() -> None:
    spec = {"id": "x/y", "license": "CC0-1.0", "providers": [
        {"name": "P", "roles": ["producer", "licensor"], "url": "https://p"},
    ]}
    providers, is_mirror = build.resolve_providers(spec, HOST)
    assert is_mirror is True, "no host role means mirror"
    assert providers[-1]["roles"] == ["host"], f"host block not last: {providers}"


def check_license_other_emits_link() -> None:
    links = build.license_links(
        {"id": "x/y", "license": "other", "license_url": "https://lic"})
    assert len(links) == 1 and links[0]["rel"] == "license", links
    assert links[0]["href"] == "https://lic", links
    assert links[0]["type"] == "text/html", links


def check_license_spdx_no_link() -> None:
    assert build.license_links({"id": "x/y", "license": "CC0-1.0"}) == []


def check_license_other_missing_url_errors() -> None:
    try:
        build.license_links({"id": "x/y", "license": "other"})
    except ValueError:
        return
    raise AssertionError("license other without license_url did not raise")


def check_findings_pass_conformant() -> None:
    obj = {
        "type": "Collection", "license": "CC0-1.0",
        "providers": [
            {"name": "P", "roles": ["producer"]},
            {"name": "H", "roles": ["host"], "url": "https://h"},
        ],
        "links": [],
    }
    assert build.collection_findings(obj) == [], build.collection_findings(obj)


def check_findings_flag_host_not_last() -> None:
    obj = {
        "type": "Collection", "license": "CC0-1.0",
        "providers": [
            {"name": "H", "roles": ["host"], "url": "https://h"},
            {"name": "P", "roles": ["producer"]},
        ],
        "links": [],
    }
    assert build.collection_findings(obj), "host-not-last should be flagged"


def check_findings_flag_missing_license_link() -> None:
    obj = {
        "type": "Collection", "license": "other",
        "providers": [
            {"name": "P", "roles": ["producer"]},
            {"name": "H", "roles": ["host"], "url": "https://h"},
        ],
        "links": [],
    }
    assert build.collection_findings(obj), "missing license link should be flagged"


def check_vector_columns_include_geometry() -> None:
    import json
    import subprocess
    import tempfile
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "properties": {"name": "a"},
             "geometry": {"type": "Polygon",
                          "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]]}},
        ],
    }
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        gj = tmp / "tiny.geojson"
        gj.write_text(json.dumps(geojson))
        norm = tmp / "tiny.gpkg"
        subprocess.run(
            ["ogr2ogr", "-t_srs", "EPSG:4326", "-f", "GPKG", "-nln", "layer",
             str(norm), str(gj)], check=True)
        out = tmp / "tiny.parquet"
        build.write_web_geoparquet(norm, out)
        cols = build.table_columns(out)
        names = {c["name"] for c in cols}
        types = {c["type"] for c in cols}
        assert "name" in names, f"attribute column missing: {cols}"
        assert any("geometry" in t for t in types), f"no geometry column typed: {cols}"


CHECKS = [
    check_official_host_moved_last,
    check_multiple_hosts_error,
    check_mirror_appends_host_last,
    check_license_other_emits_link,
    check_license_spdx_no_link,
    check_license_other_missing_url_errors,
    check_findings_pass_conformant,
    check_findings_flag_host_not_last,
    check_findings_flag_missing_license_link,
    check_vector_columns_include_geometry,
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
    print("all compliance checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
