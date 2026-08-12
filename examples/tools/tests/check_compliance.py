# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.3",
#   "duckdb>=1.5.5",
#   "jsonschema>=4.26.0",
#   "pyarrow>=25",
#   "geoparquet-io @ git+https://github.com/yharby/geoparquet-io.git@f27e53108910f19bd74a9ff4be5c7d97b104753c",
#   "rasterio>=1.5",
#   "numpy",
#   "Pillow>=11",
#   "rio-cogeo>=5.3",
# ]
# ///
"""Standalone compliance checks for the generator's pure helpers.

Imports helpers directly from the tool modules and asserts the Portolan
conformance rules the JSON schema delegates to tooling. Run:
    uv run examples/tools/tests/check_compliance.py
"""
import json
import re
import sys
import tempfile
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from stacio import (  # noqa: E402
    resolve_providers, license_links, crs_block, collection_agents_lines,
)
from convert import write_web_geoparquet, table_columns  # noqa: E402
from crs import (  # noqa: E402
    detect_vector_crs, detect_raster_crs, resolve_output_crs, assert_known_crs,
    describe_crs,
)
import glob  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]

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
        con = duckdb.connect()
        con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy=true;")
        con.execute(f"CREATE TABLE t AS SELECT name, ST_SetCRS(geom, 'EPSG:4326') AS geom "
                    f"FROM ST_Read('{gj}')")
        con.execute(f"COPY t TO '{norm}' (FORMAT GDAL, DRIVER 'GPKG', LAYER_NAME 'layer')")
        con.close()
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


def check_detect_vector_crs_non_epsg_raises() -> None:
    # A Shapefile whose geometry carries a non-EPSG authority (ESRI) must fail
    # loud rather than silently return "ESRI:<code>" against the EPSG-only
    # interface contract.
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy=true;")
    with tempfile.TemporaryDirectory() as d:
        shp = Path(d) / "esri.shp"
        con.execute(
            f"COPY (SELECT ST_SetCRS(ST_Point(0, 0), 'ESRI:54009') AS geom) "
            f"TO '{shp}' (FORMAT GDAL, DRIVER 'ESRI Shapefile')")
        con.close()
        try:
            detect_vector_crs(str(shp), None)
        except ValueError as exc:
            assert "ESRI" in str(exc), f"authority not named in error: {exc}"
            return
    raise AssertionError("a non-EPSG authority did not raise")


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


def check_to_geoparquet_shapefile_ogc_fid() -> None:
    # Shapefiles carry no explicit `fid` field, so ST_Read surfaces the
    # OGR-reserved OGC_FID column instead. This pins the round-trip that broke
    # the build in Task 9: OGC_FID must be renamed to `fid` in the canonical
    # GeoParquet, never left as OGC_FID nor dropped as a plain attribute.
    from convert import to_geoparquet
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy=true;")
    with tempfile.TemporaryDirectory() as d:
        shp = Path(d) / "pts.shp"
        con.execute(f"""
            COPY (SELECT * FROM (VALUES
                ('a', ST_SetCRS(ST_Point(0, 0), 'EPSG:4326')),
                ('b', ST_SetCRS(ST_Point(1, 1), 'EPSG:4326'))
            ) AS t(name, geom))
            TO '{shp}' (FORMAT GDAL, DRIVER 'ESRI Shapefile')
        """)
        con.close()
        out = Path(d) / "pts.parquet"
        bbox, n, norm, canon_crs = to_geoparquet(
            shp, {"media_type": "application/octet-stream"}, out, None)
        assert canon_crs == "EPSG:4326", canon_crs
        cols = table_columns(out)
        names = {c["name"] for c in cols}
        assert "fid" in names, f"OGC_FID was not renamed to fid: {cols}"
        assert "OGC_FID" not in names, f"OGC_FID column leaked through: {cols}"


def check_detect_raster_crs_rgb() -> None:
    src = glob.glob("examples/.cache/*RGB.byte.tif")
    if not src:
        print("SKIP check_detect_raster_crs_rgb, source not cached")
        return
    assert detect_raster_crs(Path(src[0])) == "EPSG:32618"


def check_detect_raster_crs_missing_raises() -> None:
    import numpy as np
    import rasterio

    with tempfile.TemporaryDirectory() as d:
        tif = Path(d) / "nocrs.tif"
        profile = {
            "driver": "GTiff", "height": 4, "width": 4, "count": 1, "dtype": "uint8",
            "transform": rasterio.transform.from_origin(0, 4, 1, 1),
        }
        with rasterio.open(tif, "w", **profile) as dst:
            dst.write(np.zeros((1, 4, 4), dtype="uint8"))
        try:
            detect_raster_crs(tif)
        except ValueError as exc:
            assert "no CRS" in str(exc), f"wrong message: {exc}"
            return
    raise AssertionError("a raster with no CRS did not raise")


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


def check_to_cog_preserves_source_crs() -> None:
    from convert import to_cog, proj_code, bands_from_cog, bbox_wgs84_raster
    src = glob.glob("examples/.cache/*RGB.byte.tif")
    if not src:
        print("SKIP check_to_cog_preserves_source_crs, source not cached")
        return
    with tempfile.TemporaryDirectory() as d:
        out = Path(d) / "rgb.tif"
        written = to_cog(Path(src[0]), out, None)
        assert written == "EPSG:32618", written
        assert proj_code(out) == "EPSG:32618"
        bands = bands_from_cog(out)
        assert len(bands) == 3 and bands[0]["data_type"] == "uint8", bands
        bb = bbox_wgs84_raster(out)
        assert -180 <= bb[0] <= 180 and -90 <= bb[1] <= 90, bb


def check_describe_crs_geographic() -> None:
    d = describe_crs("EPSG:4326")
    assert d == {"code": "EPSG:4326", "name": "WGS 84", "kind": "geographic",
                 "unit": "degree"}, d


def check_describe_crs_projected() -> None:
    d = describe_crs("EPSG:28992")
    assert d["kind"] == "projected", d
    assert d["unit"] == "metre", d
    assert d["name"] == "Amersfoort / RD New", d


def check_describe_crs_unknown_raises() -> None:
    try:
        describe_crs("EPSG:999999")
    except ValueError as exc:
        assert "unknown CRS" in str(exc), f"wrong message: {exc}"
        return
    raise AssertionError("an unresolvable CRS did not raise")


def check_crs_block_is_derived_not_authored() -> None:
    # Every fact in the block comes from the CRS registry, so a projected CRS
    # gets its linear unit and a geographic one gets the degrees warning
    # without anything in a manifest saying so.
    proj = "\n".join(crs_block("EPSG:28992", "vector", "polygon"))
    assert "## Coordinate Reference System" in proj, proj
    assert "EPSG:28992, Amersfoort / RD New" in proj, proj
    assert "projected" in proj and "metres" in proj, proj
    geog = "\n".join(crs_block("EPSG:4269", "vector", "polygon"))
    assert "EPSG:4269, NAD83" in geog, geog
    assert "geographic" in geog and "square degrees" in geog, geog


def check_crs_consequence_matches_the_geometry() -> None:
    # A measure the geometry cannot produce reads as authoritative and sends a
    # consumer after a number that is always zero. Verified in DuckDB 1.5.5,
    # ST_Area and ST_Length on a POINT both return 0.0, and ST_Area on a
    # LINESTRING returns 0.0, so only a polygon may be told about area.
    point = "\n".join(crs_block("EPSG:4326", "vector", "point"))
    assert "area" not in point.lower(), point
    assert "distance" in point, point
    line = "\n".join(crs_block("EPSG:4326", "vector", "line"))
    assert "area" not in line.lower(), line
    assert "length" in line, line
    polygon = "\n".join(crs_block("EPSG:4326", "vector", "polygon"))
    assert "square degrees" in polygon, polygon
    # A raster has no geometry column, so naming SQL measures over one is
    # meaningless. It is told about pixel size instead.
    raster = "\n".join(crs_block("EPSG:32618", "raster", None))
    assert "Pixel size" in raster, raster
    assert "functions" not in raster, raster


def check_crs_block_without_a_geometry_raises() -> None:
    # A vector Collection whose manifest omits geometry cannot be told what
    # follows from its CRS, so the build stops rather than guessing polygon
    # and shipping area advice to a point layer.
    try:
        crs_block("EPSG:4326", "vector", None)
    except ValueError as exc:
        assert "geometry" in str(exc), f"reason not given: {exc}"
        return
    raise AssertionError("a vector Collection with no geometry did not raise")


def check_crs_placeholder_renders_for_a_geospatial_collection() -> None:
    spec = {"id": "x/y", "title": "T", "license": "CC0-1.0",
            "geometry": "polygon", "docs": {"agents": "Lead.\n\n{{crs}}"}}
    facts = {"kind": "vector", "data_name": "y.parquet", "has_visual": False,
             "has_thumb": False, "crs": "EPSG:32618"}
    out = "\n".join(collection_agents_lines(spec, facts))
    assert "EPSG:32618, WGS 84 / UTM zone 18N" in out, out


def check_crs_placeholder_without_a_proj_code_raises() -> None:
    # A non-geospatial Collection has no CRS to state, so {{crs}} must fail the
    # build rather than render an empty or vague block. The placeholder is
    # simply not offered where the data asset carries no proj:code.
    spec = {"id": "tabular/t", "title": "T", "license": "CC0-1.0",
            "docs": {"agents": "Lead.\n\n{{crs}}"}}
    facts = {"kind": "tabular", "data_name": "t.parquet", "has_visual": False,
             "has_thumb": False, "crs": None}
    try:
        collection_agents_lines(spec, facts)
    except ValueError as exc:
        assert "{{crs}}" in str(exc), f"placeholder not named: {exc}"
        assert "proj:code" in str(exc), f"reason not given: {exc}"
        return
    raise AssertionError("{{crs}} on a Collection with no CRS did not raise")


def check_committed_agents_docs_state_their_crs() -> None:
    # The drift guard. Every geospatial Collection's AGENTS.md must name the
    # exact code its data asset carries, and a Collection with no proj:code
    # must not claim one. This is what issue #138 found missing.
    colls = sorted(glob.glob(str(ROOT / "examples/catalog/*/*/*/collection.json")))
    assert colls, "no committed collections found"
    for path in colls:
        coll = json.loads(Path(path).read_text())
        code = coll["assets"]["data"].get("proj:code")
        agents = (Path(path).parent / "AGENTS.md").read_text()
        cid = coll["id"]
        if code:
            assert code in agents, f"{cid} AGENTS.md never states its CRS {code}"
        else:
            assert "EPSG:" not in agents, f"{cid} has no proj:code but names an EPSG code"


def check_geodesic_examples_set_the_axis_order() -> None:
    # DuckDB's geodesic functions read the first coordinate as latitude unless
    # geometry_always_xy is set, and this catalog stores longitude first, so a
    # block that calls one without the setting publishes a wrong number that
    # still looks plausible. check_docs.py cannot catch it, because it proves a
    # block runs rather than that its answer is right. Each block gets a fresh
    # connection, so each one needs its own SET.
    axis_sensitive = ("ST_Distance_Sphere", "ST_Area_Spheroid",
                      "ST_Length_Spheroid", "ST_Perimeter_Spheroid")
    docs = sorted(glob.glob(str(ROOT / "examples/catalog/**/*.md"), recursive=True))
    assert docs, "no committed docs found"
    checked = 0
    for path in docs:
        for block in re.findall(r"```sql\n(.*?)```", Path(path).read_text(), re.S):
            if not any(fn in block for fn in axis_sensitive):
                continue
            checked += 1
            rel = Path(path).relative_to(ROOT)
            assert "SET geometry_always_xy = true;" in block, (
                f"{rel} runs a geodesic function without setting the axis "
                f"order, so its answer is wrong\n{block}")
    assert checked, "no geodesic examples found, the guard is checking nothing"


CHECKS = [
    check_official_host_moved_last,
    check_multiple_hosts_error,
    check_mirror_appends_host_last,
    check_license_other_emits_link,
    check_license_spdx_no_link,
    check_license_other_missing_url_errors,
    check_vector_columns_include_geometry,
    check_to_geoparquet_preserves_source_crs,
    check_to_geoparquet_shapefile_ogc_fid,
    check_detect_vector_crs_netherlands,
    check_detect_vector_crs_missing_raises,
    check_detect_vector_crs_present_but_no_crs,
    check_detect_vector_crs_non_epsg_raises,
    check_detect_raster_crs_rgb,
    check_detect_raster_crs_missing_raises,
    check_resolve_output_crs_precedence,
    check_assert_known_crs,
    check_to_cog_preserves_source_crs,
    check_describe_crs_geographic,
    check_describe_crs_projected,
    check_describe_crs_unknown_raises,
    check_crs_block_is_derived_not_authored,
    check_crs_consequence_matches_the_geometry,
    check_crs_block_without_a_geometry_raises,
    check_crs_placeholder_renders_for_a_geospatial_collection,
    check_crs_placeholder_without_a_proj_code_raises,
    check_committed_agents_docs_state_their_crs,
    check_geodesic_examples_set_the_axis_order,
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
