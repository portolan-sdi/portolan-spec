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
the toolchain catches that, reis does not read style bodies and the STAC
validators skip them for having no stac_version, so it is asserted here.

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
            "style": {"color": "#112233", "category_field": "region",
                      "label_field": "region", "graduated_field": "area",
                      "variants": ["categorical", "labeled", "graduated"]}}
    written = author_styles(coll / "styles", "demo", pmtiles.name, src, spec)
    assert len(written) == 3, written

    for path in written:
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


def check_default_variant_drives_the_paint(tmp: Path) -> None:
    """The first variant is the default style, and a categorical default paints
    from the category palette, which is what the thumbnail also renders."""
    src = tmp / "src2.gpkg"
    _fixture(src)
    coll = tmp / "demo2"
    coll.mkdir()

    for variants, categorical_expected in (
        (["categorical", "labeled"], True),
        (["default", "categorical"], False),
    ):
        spec = {"geometry": "polygon",
                "style": {"color": "#112233", "category_field": "region",
                          "label_field": "region", "variants": variants}}
        written = author_styles(coll / "styles", "demo2", "demo2.pmtiles", src, spec)
        first = json.loads(written[0].read_text())
        fill = first["layers"][0]["paint"]["fill-color"]
        is_categorical = isinstance(fill, list) and fill[0] == "match"
        assert is_categorical == categorical_expected, (variants, fill)
        # The thumbnail keys off the same variant name, so the two cannot drift.
        assert (variants[0] in CATEGORICAL_VARIANTS) == categorical_expected, variants


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        check_style_paths_resolve(tmp)
        check_default_variant_drives_the_paint(tmp)
    print("OK, MapLibre styles resolve their PMTiles and the default variant drives the paint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
