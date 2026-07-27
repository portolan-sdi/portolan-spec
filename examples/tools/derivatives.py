"""Derivatives, PMTiles vector tiles and MapLibre styles.

PMTiles come from tippecanoe. Styles are authored from the real field values so
the categorical palette matches the thumbnails.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from common import run
from config import PALETTE

# The style variants author_styles paints from the shared category palette. The
# thumbnail reads this so a categorical default style and the preview agree.
CATEGORICAL_VARIANTS = ("categorical", "labeled")

# MapLibre source key. formats.md names `data` as the conventional source key and
# `layers[].source` value for a PMTiles style.
SOURCE_KEY = "data"


def make_pmtiles(vector_src: Path, out_pmtiles: Path, layer_name: str) -> None:
    seq = out_pmtiles.with_suffix(".geojsonl")
    seq.unlink(missing_ok=True)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial; SET geometry_always_xy=true;")
    con.execute(f"COPY (SELECT * FROM ST_Read('{vector_src}')) "
                f"TO '{seq}' (FORMAT GDAL, DRIVER 'GeoJSONSeq')")
    con.close()
    # Run from the collection directory with bare filenames. tippecanoe records
    # both --name and the verbatim command line in the archive metadata, so
    # absolute paths here would ship the builder's home directory inside every
    # published .pmtiles file.
    run(["tippecanoe", "-o", out_pmtiles.name, "--force", "-zg",
         "--drop-densest-as-needed", "--extend-zooms-if-still-dropping",
         "--name", layer_name, "-l", layer_name, seq.name],
        cwd=out_pmtiles.parent)
    seq.unlink(missing_ok=True)


def _distinct_values(src: Path, field: str, limit: int = 48) -> list:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    rows = con.execute(
        f'SELECT "{field}" v FROM ST_Read(\'{src}\') WHERE "{field}" IS NOT NULL '
        f'GROUP BY 1 ORDER BY count(*) DESC, "{field}" ASC LIMIT {limit}').fetchall()
    con.close()
    return [r[0] for r in rows]


def _category_colors(src: Path, field: str, palette: list[str] | None = None,
                     limit: int = 48) -> list[tuple[Any, str]]:
    """Map the most common values of a field to palette colours, cycling the
    palette. Shared by the thumbnails and the MapLibre categorical styles so a
    collection reads identically across both."""
    pal = palette or PALETTE
    vals = _distinct_values(src, field, limit)
    return [(v, pal[i % len(pal)]) for i, v in enumerate(vals)]


def _numeric_stops(src: Path, field: str) -> list[float]:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    lo, mid, hi = con.execute(
        f'SELECT min("{field}"), median("{field}"), max("{field}") '
        f"FROM ST_Read('{src}')").fetchone()
    con.close()
    return [round(float(lo), 4), round(float(mid), 4), round(float(hi), 4)]


def author_styles(styles_dir: Path, layer: str, pmtiles_name: str, vector_src: Path,
                  spec: dict) -> list[Path]:
    """Author runnable MapLibre GL styles that read the collection's PMTiles from
    the collection `style` block. Categorical, labeled, and graduated variants use
    the real field values, and categorical shares the thumbnail palette."""
    styles_dir.mkdir(parents=True, exist_ok=True)
    st = spec.get("style", {}) or {}
    color = st.get("color", "#3388ff")
    outline = st.get("outline", "#ffffff")
    opacity = float(st.get("opacity", 0.6))
    geom = spec.get("geometry", "polygon")
    gl_type = {"polygon": "fill", "point": "circle", "line": "line"}[geom]
    color_key = "circle-color" if geom == "point" else "fill-color"
    palette = st.get("palette")
    category_field = st.get("category_field")
    label_field = st.get("label_field")
    graduated_field = st.get("graduated_field")
    # The style file lives in <collection>/styles/ and the PMTiles one level up in
    # <collection>/, so the url is relative FROM styles/, hence `../`. Writing
    # `./` here points at <collection>/styles/<name>.pmtiles, which does not
    # exist, and the style silently fails to load in MapLibre.
    source = {SOURCE_KEY: {"type": "vector", "url": f"pmtiles://../{pmtiles_name}"}}

    def base_paint() -> dict:
        if geom == "point":
            return {"circle-radius": 3, "circle-color": color, "circle-opacity": 0.85}
        if geom == "line":
            return {"line-color": color, "line-width": 1.2}
        return {"fill-color": color, "fill-outline-color": outline, "fill-opacity": opacity}

    def categorical_paint(field: str) -> dict:
        expr: list[Any] = ["match", ["get", field]]
        for v, hexc in _category_colors(vector_src, field, palette):
            expr += [v, hexc]
        expr.append("#cccccc")
        p = base_paint()
        p[color_key] = expr
        return p

    def graduated_paint(field: str) -> dict:
        lo, mid, hi = _numeric_stops(vector_src, field)
        p = base_paint()
        p[color_key] = ["interpolate", ["linear"], ["get", field],
                        lo, "#f7fbff", mid, "#6baed6", hi, "#08306b"]
        return p

    written = []
    for variant in st.get("variants", ["default"]):
        # `source` names the entry in `sources`, `source-layer` names the layer
        # inside the vector tiles, which is the tippecanoe layer name.
        layers = [{"id": layer, "type": gl_type, "source": SOURCE_KEY,
                   "source-layer": layer, "paint": base_paint()}]
        if variant == "categorical" and category_field:
            layers[0]["paint"] = categorical_paint(category_field)
        elif variant == "graduated" and graduated_field:
            layers[0]["paint"] = graduated_paint(graduated_field)
        elif variant == "labeled":
            if category_field:
                layers[0]["paint"] = categorical_paint(category_field)
            if label_field:
                layers.append({
                    "id": f"{layer}-labels", "type": "symbol", "source": SOURCE_KEY,
                    "source-layer": layer,
                    "layout": {"text-field": ["get", label_field],
                               "text-size": 11, "text-anchor": "center"},
                    "paint": {"text-color": "#222222", "text-halo-color": "#ffffff",
                              "text-halo-width": 1},
                })
        style = {"version": 8, "name": f"{layer} {variant}",
                 "sources": source, "layers": layers}
        pth = styles_dir / f"{variant}.json"
        pth.write_text(json.dumps(style, indent=2) + "\n")
        written.append(pth)
    return written
