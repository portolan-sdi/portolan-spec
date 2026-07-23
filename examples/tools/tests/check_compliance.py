# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.3",
#   "duckdb>=1.5.4",
#   "jsonschema>=4.26.0",
#   "pyarrow>=24",
#   "geoparquet-io @ git+https://github.com/yharby/geoparquet-io.git@f27e53108910f19bd74a9ff4be5c7d97b104753c",
#   "rasterio>=1.4",
# ]
# ///
"""Standalone compliance checks for the generator's pure helpers.

Imports helpers directly from the tool modules and asserts the Portolan
conformance rules the JSON schema delegates to tooling. Run:
    uv run examples/tools/tests/check_compliance.py
"""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stacio import resolve_providers, license_links  # noqa: E402
from convert import write_web_geoparquet, table_columns  # noqa: E402
from validate import collection_findings  # noqa: E402
from crs import detect_vector_crs, detect_raster_crs, resolve_output_crs, assert_known_crs  # noqa: E402
import glob  # noqa: E402

HOST = {"name": "Portolan SDI", "url": "https://github.com/portolan-sdi",
        "email": "portolan@googlegroups.com"}


def check_official_host_moved_last() -> None:
    spec = {"id": "x/y", "license": "CC0-1.0", "providers": [
        {"name": "H", "roles": ["producer", "host"], "url": "https://h"},
        {"name": "P", "roles": ["processor"]},
    ]}
    providers, is_mirror = resolve_providers(spec, HOST)
    assert is_mirror is False, "producer-host collection is official"
    assert providers[-1]["name"] == "H", f"host not last: {providers}"


def check_multiple_hosts_error() -> None:
    spec = {"id": "x/y", "license": "CC0-1.0", "providers": [
        {"name": "H1", "roles": ["host"], "url": "https://h1"},
        {"name": "H2", "roles": ["producer", "host"], "url": "https://h2"},
    ]}
    try:
        resolve_providers(spec, HOST)
    except ValueError:
        return
    raise AssertionError("two host providers did not raise ValueError")


def check_mirror_appends_host_last() -> None:
    spec = {"id": "x/y", "license": "CC0-1.0", "providers": [
        {"name": "P", "roles": ["producer", "licensor"], "url": "https://p"},
    ]}
    providers, is_mirror = resolve_providers(spec, HOST)
    assert is_mirror is True, "no host role means mirror"
    assert providers[-1]["roles"] == ["host"], f"host block not last: {providers}"


def check_license_other_emits_link() -> None:
    links = license_links(
        {"id": "x/y", "license": "other", "license_url": "https://lic"})
    assert len(links) == 1 and links[0]["rel"] == "license", links
    assert links[0]["href"] == "https://lic", links
    assert links[0]["type"] == "text/html", links


def check_license_spdx_no_link() -> None:
    assert license_links({"id": "x/y", "license": "CC0-1.0"}) == []


def check_license_other_missing_url_errors() -> None:
    try:
        license_links({"id": "x/y", "license": "other"})
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
    assert collection_findings(obj) == [], collection_findings(obj)


def check_findings_flag_host_not_last() -> None:
    obj = {
        "type": "Collection", "license": "CC0-1.0",
        "providers": [
            {"name": "H", "roles": ["host"], "url": "https://h"},
            {"name": "P", "roles": ["producer"]},
        ],
        "links": [],
    }
    assert collection_findings(obj), "host-not-last should be flagged"


def check_findings_flag_missing_license_link() -> None:
    obj = {
        "type": "Collection", "license": "other",
        "providers": [
            {"name": "P", "roles": ["producer"]},
            {"name": "H", "roles": ["host"], "url": "https://h"},
        ],
        "links": [],
    }
    assert collection_findings(obj), "missing license link should be flagged"


def check_vector_columns_include_geometry() -> None:
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
        write_web_geoparquet(norm, out)
        cols = table_columns(out)
        names = {c["name"] for c in cols}
        types = {c["type"] for c in cols}
        assert "name" in names, f"attribute column missing: {cols}"
        assert any("geometry" in t for t in types), f"no geometry column typed: {cols}"


def check_detect_vector_crs_netherlands() -> None:
    src = glob.glob("examples/.cache/*BestuurlijkeGebieden*.gpkg")
    if not src:
        print("SKIP check_detect_vector_crs_netherlands, source not cached")
        return
    assert detect_vector_crs(src[0], "provinciegebied") == "EPSG:28992"


def check_detect_vector_crs_missing_raises() -> None:
    with tempfile.TemporaryDirectory() as d:
        # a bare CSV of WKT has no CRS, ST_Read_Meta returns none
        p = Path(d) / "nocrs.csv"
        p.write_text("geom\n\"POINT(0 0)\"\n")
        try:
            detect_vector_crs(str(p), None)
        except ValueError:
            return
    raise AssertionError("a source with no CRS did not raise")


def check_detect_vector_crs_present_but_no_crs() -> None:
    # a Shapefile written from a bare geometry with no ST_SetCRS call has a
    # real geometry field but no .prj, so ST_Read_Meta reports crs as None.
    # This must drive the "declares no CRS" branch, distinct from the
    # "no readable geometry layer" branch covered above.
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    with tempfile.TemporaryDirectory() as d:
        shp = Path(d) / "nocrs.shp"
        con.execute(
            f"COPY (SELECT ST_Point(0, 0) AS geom) TO '{shp}' "
            "(FORMAT GDAL, DRIVER 'ESRI Shapefile')")
        con.close()
        try:
            detect_vector_crs(str(shp), None)
        except ValueError as exc:
            assert "declares no CRS" in str(exc), f"wrong branch raised: {exc}"
            return
    raise AssertionError("a geometry layer that declares no CRS did not raise")


def check_to_geoparquet_preserves_source_crs() -> None:
    from convert import to_geoparquet
    srcs = glob.glob("examples/.cache/*BestuurlijkeGebieden*.gpkg")
    if not srcs:
        print("SKIP check_to_geoparquet_preserves_source_crs, source not cached")
        return
    spec_source = {"media_type": "application/geopackage+sqlite3", "layer": "provinciegebied"}
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "nl.parquet"
        bbox, n, norm, canon_crs = to_geoparquet(Path(srcs[0]), spec_source, out, None)
        assert canon_crs == "EPSG:28992", canon_crs
        con = duckdb.connect()
        con.execute("LOAD spatial;")
        pcrs = con.execute(
            f"SELECT ST_CRS(geom) FROM read_parquet('{out}') LIMIT 1").fetchone()[0]
        con.close()
        assert pcrs == "EPSG:28992", pcrs
        assert -180 <= bbox[0] <= 180 and -90 <= bbox[1] <= 90, bbox  # bbox is WGS84


def check_detect_raster_crs_rgb() -> None:
    src = glob.glob("examples/.cache/*RGB.byte.tif")
    if not src:
        print("SKIP check_detect_raster_crs_rgb, source not cached")
        return
    assert detect_raster_crs(Path(src[0])) == "EPSG:32618"


def check_resolve_output_crs_precedence() -> None:
    assert resolve_output_crs({}, None) is None
    assert resolve_output_crs({}, "EPSG:4326") == "EPSG:4326"
    assert resolve_output_crs({"output_crs": "EPSG:3857"}, "EPSG:4326") == "EPSG:3857"


def check_assert_known_crs() -> None:
    assert_known_crs("EPSG:4326")  # no raise
    try:
        assert_known_crs("EPSG:999999")
    except ValueError:
        return
    raise AssertionError("an unknown CRS did not raise")


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
    check_to_geoparquet_preserves_source_crs,
    check_detect_vector_crs_netherlands,
    check_detect_vector_crs_missing_raises,
    check_detect_vector_crs_present_but_no_crs,
    check_detect_raster_crs_rgb,
    check_resolve_output_crs_precedence,
    check_assert_known_crs,
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
