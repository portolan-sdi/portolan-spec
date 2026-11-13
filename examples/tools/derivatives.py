"""Derivatives, PMTiles vector tiles and MapLibre styles.

PMTiles come from tippecanoe. Styles are authored from the real field values so
the categorical palette matches the thumbnails. Each manifest style variant is
a dict naming its own type and field, so one collection can ship a categorical
style, a graduated ramp, a heatmap, and a labeled variant side by side.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb

from common import run
from config import PALETTE

# Variant types the thumbnail can paint from the shared category palette. A
# default variant of any other type paints flat, and the thumbnail must too.
CATEGORICAL_VARIANTS = ("categorical",)

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


def _read_expr(src: Path) -> str:
    """The DuckDB relation that reads a sampling source. Styles are sampled from
    the WGS84 GeoPackage intermediate during a full build, and straight from the
    committed GeoParquet during a styles-only regeneration. Only attribute
    values are read, so the CRS difference does not matter."""
    if src.suffix == ".parquet":
        return f"read_parquet('{src}')"
    return f"ST_Read('{src}')"


def _distinct_values(src: Path, field: str, limit: int = 48,
                     sort: str = "count") -> list:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    order = f'"{field}" ASC' if sort == "value" else f'count(*) DESC, "{field}" ASC'
    rows = con.execute(
        f'SELECT "{field}" v FROM {_read_expr(src)} WHERE "{field}" IS NOT NULL '
        f'GROUP BY 1 ORDER BY {order} LIMIT {limit}').fetchall()
    con.close()
    return [r[0] for r in rows]


def _category_colors(src: Path, field: str, palette: list[str] | None = None,
                     limit: int = 48, sort: str = "count") -> list[tuple[Any, str]]:
    """Map the values of a field to palette colours, cycling the palette. Shared
    by the thumbnails and the MapLibre categorical styles so a collection reads
    identically across both. `sort` is `count` for most-common-first, or `value`
    for the field's own ordering, which suits ordinal categories like income
    groups."""
    pal = palette or PALETTE
    vals = _distinct_values(src, field, limit, sort)
    return [(v, pal[i % len(pal)]) for i, v in enumerate(vals)]


def _quartile_breaks(src: Path, field: str) -> list[float]:
    """Class breaks at the quartiles, the default for a graduated variant that
    declares none. Quartiles beat min/median/max on skewed fields, every class
    holds a quarter of the features."""
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    q1, q2, q3 = con.execute(
        f'SELECT quantile_cont("{field}", 0.25), quantile_cont("{field}", 0.5), '
        f'quantile_cont("{field}", 0.75) FROM {_read_expr(src)}').fetchone()
    con.close()
    return [round(float(q1), 4), round(float(q2), 4), round(float(q3), 4)]


# Default sequential ramp, light to dark blue, one colour per class, used when
# a graduated variant does not bring its own.
DEFAULT_RAMP = ["#eff3ff", "#bdd7e7", "#6baed6", "#2171b5"]


def _step(input_expr: list, base: Any, breaks: list[float],
          outputs: list[Any]) -> list:
    """A MapLibre step expression, `base` below the first break, then one
    output per break. Graduated styles bin into steps rather than a continuous
    interpolate, because classed fills read better at a glance and because a
    step expression is mechanically summarizable into a legend, which clients
    like portolan-browser derive from the style body."""
    expr: list[Any] = ["step", input_expr, base]
    for b, out in zip(breaks, outputs):
        expr += [b, out]
    return expr


def author_styles(styles_dir: Path, layer: str, source_url: str, vector_src: Path,
                  spec: dict) -> list[tuple[Path, dict]]:
    """Author runnable MapLibre GL styles from the collection `style` block.

    Each entry in `style.variants` is a dict, `{name, title?, description?,
    type, field?, ...}`, and becomes one styles/<name>.json plus one
    (path, variant) pair in the return value, in manifest order. The first
    variant is the default. Categorical variants share the thumbnail palette,
    graduated variants ramp over real or declared stops, `heatmap` and
    `outline` swap the layer type, and `expression` takes raw MapLibre
    expressions from the manifest for the cases no generator shorthand covers.
    Any variant may add a label layer with `labels`.

    `source_url` is the relative path FROM styles/ to whatever the style draws,
    `../<name>.pmtiles` when the collection ships a visual derivative, or the
    GeoParquet itself for a collection that renders from source, which clients
    like portolan-browser bind onto the data they loaded."""
    styles_dir.mkdir(parents=True, exist_ok=True)
    st = spec.get("style", {}) or {}
    color = st.get("color", "#3388ff")
    outline = st.get("outline", "#ffffff")
    opacity = float(st.get("opacity", 0.6))
    geom = spec.get("geometry", "polygon")
    gl_type = {"polygon": "fill", "point": "circle", "line": "line"}[geom]
    color_key = "circle-color" if geom == "point" else "fill-color"
    is_tiles = source_url.endswith(".pmtiles")
    if is_tiles:
        source = {SOURCE_KEY: {"type": "vector", "url": f"pmtiles://{source_url}"}}
    else:
        # A collection that renders from source has no tiles for MapLibre to
        # fetch, so the source names the data file the style paints. A Portolan
        # client binds the style onto the data it loaded from that asset.
        source = {SOURCE_KEY: {"type": "vector", "url": source_url}}

    def layer_dict(ltype: str, paint: dict, suffix: str = "",
                   layout: dict | None = None, filt: list | None = None) -> dict:
        d: dict[str, Any] = {"id": f"{layer}{suffix}", "type": ltype,
                             "source": SOURCE_KEY, "paint": paint}
        if is_tiles:
            d["source-layer"] = layer
        if layout:
            d["layout"] = layout
        if filt:
            d["filter"] = filt
        return d

    def base_paint(v: dict) -> dict:
        c = v.get("color", color)
        if geom == "point":
            return {"circle-radius": v.get("radius", 3), "circle-color": c,
                    "circle-opacity": 0.85}
        if geom == "line":
            return {"line-color": c, "line-width": 1.2}
        return {"fill-color": c, "fill-outline-color": outline,
                "fill-opacity": float(v.get("opacity", opacity))}

    def variant_layers(v: dict) -> list[dict]:
        vtype = v.get("type", "flat")
        field = v.get("field")
        paint = base_paint(v)
        if vtype == "categorical":
            expr: list[Any] = ["match", ["get", field]]
            for val, hexc in _category_colors(vector_src, field, v.get("palette"),
                                              sort=v.get("sort", "count")):
                expr += [val, hexc]
            expr.append("#cccccc")
            paint[color_key] = expr
            layers = [layer_dict(gl_type, paint)]
        elif vtype == "graduated":
            breaks = v.get("breaks") or _quartile_breaks(vector_src, field)
            ramp = v.get("ramp") or DEFAULT_RAMP
            if len(ramp) != len(breaks) + 1:
                raise ValueError(
                    f"{layer} variant {v.get('name')} has {len(breaks)} breaks "
                    f"and {len(ramp)} ramp colours, a ramp needs one colour "
                    "per class, breaks plus one")
            paint[color_key] = _step(["get", field], ramp[0], breaks, ramp[1:])
            if geom == "point" and v.get("radius_range"):
                r0, r1 = v["radius_range"]
                n = len(ramp)
                radii = [round(r0 + (r1 - r0) * i / (n - 1), 1) for i in range(n)]
                paint["circle-radius"] = _step(["get", field], radii[0],
                                               breaks, radii[1:])
            layers = [layer_dict(gl_type, paint)]
        elif vtype == "heatmap":
            layers = [layer_dict("heatmap", {
                "heatmap-radius": v.get("heatmap_radius", 18),
                "heatmap-opacity": 0.8,
            })]
        elif vtype == "outline":
            layers = [layer_dict("line", {
                "line-color": v.get("color", color),
                "line-width": v.get("width", 1.5),
            })]
        elif vtype == "expression":
            # The escape hatch. The manifest carries raw MapLibre expressions
            # for the paint keys no shorthand covers, a case over a flag
            # column, an arithmetic ratio, a bespoke highlight.
            for key, expr in (v.get("paint") or {}).items():
                paint[key] = expr
            layers = [layer_dict(gl_type, paint)]
        else:  # flat
            layers = [layer_dict(gl_type, paint)]
        labels = v.get("labels")
        if labels:
            layers.append(layer_dict(
                "symbol",
                {"text-color": "#222222", "text-halo-color": "#ffffff",
                 "text-halo-width": 1},
                suffix="-labels",
                layout={"text-field": ["get", labels["field"]],
                        "text-size": labels.get("size", 11),
                        "text-anchor": "center"},
                filt=labels.get("filter")))
        return layers

    written = []
    for v in st.get("variants") or [{"name": "default", "type": "flat"}]:
        style: dict[str, Any] = {
            "version": 8,
            "name": v.get("title") or f"{layer} {v['name']}",
            "sources": source,
            "layers": variant_layers(v),
        }
        if v.get("description"):
            # styling.md asks each style to explain what its colours represent.
            style["metadata"] = {"description": v["description"]}
        pth = styles_dir / f"{v['name']}.json"
        pth.write_text(json.dumps(style, ensure_ascii=False, indent=2) + "\n")
        written.append((pth, v))
    return written
