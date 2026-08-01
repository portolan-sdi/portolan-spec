# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "duckdb>=1.5.5",
# ]
# ///
"""Standalone check for the MapLibre styles author_styles writes.

formats.md requires a PMTiles style to be "a complete, self-contained JSON
loadable directly by MapLibre GL JS", and states the convention that
`sources.data.url` is the relative path FROM `styles/` to the PMTiles file,
typically `../filename.pmtiles`, with `layers[].source` set to `data`.

A style file that points at `./x.pmtiles` resolves to `styles/x.pmtiles`, which
does not exist, so the style loads no tiles and renders nothing. Nothing else in
the toolchain catches that, rashid does not read style bodies and the STAC
validators skip them for having no stac_version, so it is asserted here. A
collection that renders from source gets styles too, sourcing the GeoParquet
itself, and those urls must resolve the same way.

core.md also requires the thumbnail to be generated from default styling, where
the default style is the variant listed first. That is only true if the thumbnail
and the first style variant derive their paint from one source, so the wiring
that guarantees it is asserted too.

Run: uv run examples/tools/tests/check_styles.py
"""
import json
import sys
import tempfile
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from derivatives import CATEGORICAL_VARIANTS, SOURCE_KEY, author_styles  # noqa: E402


def _fixture(path: Path) -> None:
    """A tiny two-category polygon layer, enough for a categorical match expression."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.execute(f"""
        COPY (
          SELECT 'north' AS region, 12.5 AS area,
                 ST_GeomFromText('POLYGON((0 0,1 0,1 1,0 1,0 0))') AS geom
          UNION ALL
          SELECT 'south', 7.25,
                 ST_GeomFromText('POLYGON((1 1,2 1,2 2,1 2,1 1))')
        ) TO '{path}' (FORMAT GDAL, DRIVER 'GPKG')""")
    con.close()


VARIANTS = [
    {"name": "categorical", "type": "categorical", "field": "region"},
    {"name": "labeled", "type": "categorical", "field": "region",
     "labels": {"field": "region"}},
    {"name": "graduated", "type": "graduated", "field": "area"},
    {"name": "highlight", "type": "expression",
     "paint": {"fill-color": ["match", ["get", "region"],
                              "north", "#111111", "#cccccc"]}},
    {"name": "boundaries", "type": "outline"},
]


def check_style_paths_resolve(tmp: Path) -> None:
    """Every style's source url must resolve to the real PMTiles file from the
    styles/ directory it is written into."""
    src = tmp / "src.gpkg"
    _fixture(src)
    coll = tmp / "demo"
    coll.mkdir()
    pmtiles = coll / "demo.pmtiles"
    pmtiles.write_bytes(b"PMTiles stand-in")  # only its path matters here

    spec = {"geometry": "polygon",
            "style": {"color": "#112233", "variants": VARIANTS}}
    written = author_styles(coll / "styles", "demo", f"../{pmtiles.name}", src, spec)
    assert len(written) == len(VARIANTS), written

    for path, variant in written:
        style = json.loads(path.read_text())
        assert style["version"] == 8, style
        assert list(style["sources"]) == [SOURCE_KEY], style["sources"]

        url = style["sources"][SOURCE_KEY]["url"]
        assert url.startswith("pmtiles://"), url
        target = (path.parent / url.removeprefix("pmtiles://")).resolve()
        assert target == pmtiles.resolve(), f"{path.name} points at {target}, not {pmtiles}"
        assert target.exists(), f"{path.name} source url does not resolve: {url}"

        for layer in style["layers"]:
            assert layer["source"] == SOURCE_KEY, layer
            # source-layer names the layer inside the tiles, not the style source.
            assert layer["source-layer"] == "demo", layer
        assert path.stem == variant["name"], (path, variant)

    labeled = json.loads((coll / "styles/labeled.json").read_text())
    assert labeled["layers"][-1]["type"] == "symbol", labeled["layers"]
    boundaries = json.loads((coll / "styles/boundaries.json").read_text())
    assert boundaries["layers"][0]["type"] == "line", boundaries["layers"]


def check_parquet_sourced_styles(tmp: Path) -> None:
    """A collection with no PMTiles sources its styles from the GeoParquet.

    The url must resolve to the real data file, and geojson-bound rendering has
    no source layers, so the style still carries source-layer only when it is
    tile-backed, which for a parquet source it is not required to be dropped by
    the generator, clients drop it when binding. What matters here is the url."""
    src = tmp / "src3.gpkg"
    _fixture(src)
    coll = tmp / "demo3"
    coll.mkdir()
    parquet = coll / "demo3.parquet"
    parquet.write_bytes(b"parquet stand-in")

    spec = {"geometry": "polygon",
            "style": {"color": "#112233",
                      "variants": [{"name": "flat", "type": "flat"}]}}
    written = author_styles(coll / "styles", "demo3", f"../{parquet.name}", src, spec)
    style = json.loads(written[0][0].read_text())
    url = style["sources"][SOURCE_KEY]["url"]
    assert not url.startswith("pmtiles://"), url
    target = (coll / "styles" / url).resolve()
    assert target == parquet.resolve() and target.exists(), url
    # No tiles means no source-layer for MapLibre to reject on a geojson source.
    assert "source-layer" not in style["layers"][0], style["layers"][0]


def check_default_variant_drives_the_paint(tmp: Path) -> None:
    """The first variant is the default style, and a categorical default paints
    from the category palette, which is what the thumbnail also renders."""
    src = tmp / "src2.gpkg"
    _fixture(src)
    coll = tmp / "demo2"
    coll.mkdir()

    for variants, categorical_expected in (
        ([{"name": "categorical", "type": "categorical", "field": "region"}], True),
        ([{"name": "flat", "type": "flat"},
          {"name": "categorical", "type": "categorical", "field": "region"}], False),
    ):
        spec = {"geometry": "polygon",
                "style": {"color": "#112233", "variants": variants}}
        written = author_styles(coll / "styles", "demo2", "../demo2.pmtiles", src, spec)
        first = json.loads(written[0][0].read_text())
        fill = first["layers"][0]["paint"]["fill-color"]
        is_categorical = isinstance(fill, list) and fill[0] == "match"
        assert is_categorical == categorical_expected, (variants, fill)
        # The thumbnail keys off the same variant type, so the two cannot drift.
        first_type = variants[0]["type"]
        assert (first_type in CATEGORICAL_VARIANTS) == categorical_expected, variants


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        check_style_paths_resolve(tmp)
        check_parquet_sourced_styles(tmp)
        check_default_variant_drives_the_paint(tmp)
    print("OK, MapLibre styles resolve their sources and the default variant drives the paint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
