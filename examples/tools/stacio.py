"""STAC assembly, manifest, providers, assets, links, sidecars, and the
collection and catalog builders.
"""
from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from common import filesize, multihash
from config import (
    SCHEMA_URI, FILE_EXT, WEBMAP_EXT, TABLE_EXT, PROJ_EXT,
    ATTRIBUTION_EXT, STAC_VERSION, MEDIA, ICON_TYPES,
)
from fetch import fetch
from crs import resolve_output_crs, describe_crs
from convert import (
    to_geoparquet, feature_count, to_cog, bands_from_cog,
    bbox_wgs84_raster, to_table_parquet, table_columns,
)
from derivatives import make_pmtiles, author_styles, CATEGORICAL_VARIANTS
from thumbnails import (
    make_thumbnail_vector, make_thumbnail_raster, build_thumb_ctx, _thumb_desc,
)


# --------------------------------------------------------------------- manifest
def load_manifest(path: Path) -> dict:
    m = yaml.safe_load(path.read_text())
    assert m["schema_uri"] == SCHEMA_URI, "manifest schema_uri must be the pinned v0.2.0 URI"
    logo = m.get("logo")
    if logo:
        # The manifest directory is the only place that knows where a relative
        # logo source points, and build_catalog never sees the manifest path.
        logo["path"] = (path.parent / logo["source"]).resolve()
    return m


def resolve_providers(spec: dict, host: dict) -> tuple[list[dict], bool]:
    """Return (providers, is_mirror), guaranteeing exactly one host, listed last.

    A producer that also hosts makes the collection official, and that host
    provider is moved to the last position. A collection with no host role is a
    mirror, and the Portolan host block is appended last. More than one host role
    is a manifest error."""
    providers = [dict(p) for p in spec["providers"]]
    host_idx = [i for i, p in enumerate(providers) if "host" in p.get("roles", [])]
    if len(host_idx) > 1:
        raise ValueError(
            f"{spec.get('id')} lists {len(host_idx)} host providers, exactly one is allowed")
    if host_idx:
        i = host_idx[0]
        if i != len(providers) - 1:
            providers.append(providers.pop(i))
        return providers, False
    host_block = {k: v for k, v in host.items() if v}
    host_block["roles"] = ["host"]
    return providers + [host_block], True


def check_provenance(spec: dict, is_mirror: bool) -> None:
    prov = spec.get("provenance", {}) or {}
    if is_mirror:
        assert prov.get("via"), f"{spec['id']} is a mirror and needs provenance.via"
        assert prov.get("updated"), f"{spec['id']} is a mirror and needs provenance.updated"


# ----------------------------------------------------------------- stac helpers
def link(rel: str, href: str, type_: str, title: str | None = None, extra: dict | None = None) -> dict:
    d = {"rel": rel, "href": href, "type": type_}
    if title:
        d["title"] = title
    if extra:
        d.update(extra)
    return d


def license_links(spec: dict) -> list[dict]:
    """Return the rel=license link required when the license is `other`.

    The spec makes a license link mandatory when `license` is the STAC value
    `other`, pointing to the license text. For any SPDX identifier no link is
    needed, so this returns an empty list."""
    if spec.get("license") != "other":
        return []
    url = spec.get("license_url")
    if not url:
        raise ValueError(
            f"{spec.get('id')} has license 'other' but no license_url in the manifest")
    return [link("license", url, "text/html", "License")]


def asset(path: Path, media: str, roles: list[str], title: str, extra: dict | None = None) -> dict:
    a: dict[str, Any] = {"href": f"./{path.name}", "type": media, "title": title,
                         "roles": roles, "file:size": filesize(path), "file:checksum": multihash(path)}
    if extra:
        a.update(extra)
    return a


def style_asset(path: Path, variant: dict, default: bool = False) -> dict:
    # core.md marks the default style with a second role, not by key or position,
    # because STAC assets are an unordered object whose keys carry no meaning a
    # client is expected to understand. Multiple roles per asset are standard STAC.
    roles = ["style", "default"] if default else ["style"]
    title = variant.get("title") or f"{variant['name'].capitalize()} MapLibre style"
    a = {"href": f"./styles/{path.name}", "type": MEDIA["style"],
         "title": title, "roles": roles,
         "file:size": filesize(path), "file:checksum": multihash(path)}
    if variant.get("description"):
        a["description"] = variant["description"]
    return a


def add_style_assets(assets: dict, coll_dir: Path, layer_name: str,
                     source_url: str, sample_src: Path, spec: dict) -> None:
    """Author the style variants and register them as assets, first as default.

    Any style-* asset already present is dropped first, and any styles/*.json
    the manifest no longer names is deleted, so a rename cannot strand a stale
    style on disk or in the metadata."""
    for key in [k for k in assets if k.startswith("style-")]:
        del assets[key]
    written = author_styles(coll_dir / "styles", layer_name, source_url,
                            sample_src, spec)
    keep = {p.name for p, _ in written}
    for stale in (coll_dir / "styles").glob("*.json"):
        if stale.name not in keep:
            stale.unlink()
    for i, (pth, variant) in enumerate(written):
        assets[f"style-{variant['name']}"] = style_asset(pth, variant, default=i == 0)


def thumb_style(spec: dict) -> dict:
    """The paint context the thumbnail renders from.

    core.md requires the thumbnail to be generated from default styling, and the
    default style is the first variant, the one published with the default role.
    The thumbnail paints categories only when that first variant is categorical,
    from the same field and palette, so the preview and styles/<first>.json
    cannot drift apart."""
    st = spec.get("style") or {}
    first = (st.get("variants") or [{}])[0]
    ctx = {**st, "geometry": spec.get("geometry", "polygon"),
           "default_variant": first.get("type", "default")}
    if first.get("type") in CATEGORICAL_VARIANTS:
        ctx["category_field"] = first.get("field")
        if first.get("palette"):
            ctx["palette"] = first["palette"]
    else:
        ctx.pop("category_field", None)
    return ctx


def source_asset(local: Path, spec_source: dict) -> dict:
    """The upstream original, cited alongside the cloud-native asset.

    It does NOT carry the `data` role. core.md scopes `data` to the primary
    GeoParquet, COG, or Parquet, and says the cloud-native asset is the primary
    while the rest are alternates. A zipped Shapefile, a GeoPackage, or a CSV is
    none of those, and rolling it `data` would leave a client filtering on that
    role unable to tell which asset is canonical."""
    return {"href": spec_source["url"], "type": spec_source["media_type"],
            "title": spec_source["title"], "roles": ["source"],
            "file:size": filesize(local), "file:checksum": multihash(local)}


def add_metadata_asset(assets: dict, spec: dict, coll_dir: Path, cache: Path) -> None:
    """Mirror an upstream machine-readable metadata record beside the data.

    core.md's Metadata section asks collections to ship machine-readable
    metadata where it exists. The record is mirrored into the collection rather
    than referenced by URL, because a registry regenerates its XML, and a
    checksum pinned to bytes the catalog does not control is guaranteed to rot,
    the same reasoning that keeps live endpoints out of the source assets. The
    fetch happens once, an existing local copy is reused."""
    meta = spec.get("metadata")
    if not meta:
        return
    dest = coll_dir / meta.get("filename", "iso19115.xml")
    if not dest.exists():
        import shutil
        local = fetch(meta["url"], cache, stable=True)
        shutil.copyfile(local, dest)
    roles = ["metadata"] + ([meta["standard"]] if meta.get("standard") else [])
    assets["metadata"] = asset(dest, meta.get("media_type", "application/xml"),
                               roles, meta["title"])


def add_source_asset(assets: dict, local: Path, spec_source: dict) -> None:
    """Attach the `source` Asset, but only for a stable upstream download.

    formats.md scopes the rule to an original that is "directly downloadable (not
    just an API)", so a `stable: false` upstream gets no `source` Asset at all. It
    is referenced by URL in the sidecars instead. Two reasons. A live query URL is
    an API rather than a download, and `file:size` and `file:checksum` pinned to
    bytes this catalog does not control are guaranteed to rot the moment upstream
    changes, which is exactly the validator failure rashid caught on the Socrata
    mirror.
    """
    if spec_source.get("stable", True):
        assets["source"] = source_asset(local, spec_source)


# --------------------------------------------------------------- prose sidecars
def _providers_sentence(providers: list[dict]) -> str:
    parts = [f"{p['name']} ({', '.join(p.get('roles', []))})" for p in providers]
    return ", ".join(parts)


def describe_columns(cols: list[dict], descriptions: dict) -> list[dict]:
    """Merge manifest-authored column descriptions into the derived schema.

    A Parquet footer carries names and types but no semantics, so the prose has to
    come from the manifest. core.md and formats.md both ask for column
    descriptions, and for a tabular collection the column schema is the only
    semantic handle a consumer gets."""
    if not descriptions:
        return cols
    out = []
    for c in cols:
        desc = descriptions.get(c["name"])
        out.append({**c, "description": desc} if desc else dict(c))
    return out


def join_section(join: dict) -> list[str]:
    """Render the README join documentation for a table that has to be joined to a
    geometry collection to be mapped.

    formats.md requires the join columns to be named explicitly and a working code
    example to be shown whenever geometry and attributes live in separate files."""
    if not join:
        return []
    lines = [
        "## Join to Geometry",
        "",
        f"This table carries no geometry. Join it to `{join['target']}` to map it.",
        "",
        f"- This table's join column, `{join['column']}`.",
        f"- Geometry collection, `{join['target']}`, join column `{join['target_column']}`.",
        "",
    ]
    if join.get("note"):
        lines += [join["note"].strip(), ""]
    lines += [
        "```sql",
        "INSTALL spatial; LOAD spatial;",
        "SELECT t.*, g.geom",
        f"FROM read_parquet('{join['this_file']}') t",
        f"JOIN read_parquet('{join['target_file']}') g",
        f"  ON t.\"{join['column']}\" = g.\"{join['target_column']}\";",
        "```",
    ]
    return lines


def quickstart_block(kind: str, data_name: str) -> list[str]:
    """The one runnable snippet that opens the cloud-native data asset, chosen by
    kind. One tested snippet beats four aspirational ones, so the README gets a
    single Quick Start and the agent guide carries the deeper query patterns."""
    if kind == "vector":
        return [
            "```python",
            "import geopandas as gpd",
            "",
            f'gdf = gpd.read_parquet("{data_name}")',
            "print(gdf.head())",
            "```",
            "",
            "The `data` asset is GeoParquet 2.0 with a native geometry type and a "
            "covering bbox column, so it needs a GeoPandas built on pyarrow 24 or "
            "newer. DuckDB spatial queries the same file in place, see "
            "[AGENTS.md](./AGENTS.md) for those patterns. Paths are relative to "
            "this directory, and the same code works against the published URL.",
        ]
    if kind == "raster":
        return [
            "```python",
            "import rioxarray",
            "",
            f'da = rioxarray.open_rasterio("{data_name}", masked=True)',
            "print(da)",
            "```",
            "",
            "The `data` asset is a Cloud Optimized GeoTIFF, so the same call "
            "against the published URL streams only the bytes it needs over HTTP "
            "range requests. Pass masked=True so nodata reads as NaN.",
        ]
    # tabular
    return [
        "```python",
        "import pandas as pd",
        "",
        f'df = pd.read_parquet("{data_name}")',
        "print(df.head())",
        "```",
        "",
        "The `data` asset is plain Parquet, so pandas, DuckDB, and Polars all "
        "read it directly. Paths are relative to this directory, and the same "
        "code works against the published URL.",
    ]


def access_line(kind: str, data_name: str, has_visual: bool, has_thumb: bool) -> str:
    """The one-line access guidance for AGENTS.md, chosen by kind."""
    if kind == "vector":
        line = ("Query the GeoParquet `data` asset in place with DuckDB spatial, "
                f"read_parquet('{data_name}'), or load it with GeoPandas. It streams "
                "over HTTP range requests, so query the published URL directly "
                "rather than downloading first.")
    elif kind == "raster":
        line = (f'Read the COG `data` asset with rioxarray.open_rasterio("{data_name}", '
                "masked=True) or rasterio. It serves windowed reads and overviews "
                "over HTTP range requests, so read the window you need rather than "
                "the whole file.")
    else:
        line = (f"Query the Parquet `data` asset in place with DuckDB, "
                f"read_parquet('{data_name}'), or load it with pandas.")
    if has_visual:
        line += " For rendering use the visual PMTiles asset with its MapLibre styles."
    elif has_thumb:
        line += " For a quick preview use the thumbnail asset."
    return line


def schema_block(cols: list[dict]) -> list[str]:
    """A schema table of the described columns, generated from the same
    `table:columns` the collection carries, so prose and metadata cannot drift."""
    described = [c for c in cols if c.get("description")]
    if not described:
        return []
    lines = ["| Column | Type | Description |", "|---|---|---|"]
    for c in described:
        lines.append(f"| `{c['name']}` | {c['type']} | {c['description']} |")
    lines.append("")
    if len(described) < len(cols):
        lines.append(f"The table has {len(cols)} columns in all. The full list "
                     "with types lives in `table:columns` on the collection.")
    else:
        lines.append("The same descriptions live in `table:columns` on the "
                     "collection, so tools that read STAC see them too.")
    return lines


# PROJ names an axis unit in the singular. Only the units that actually appear
# on an EPSG horizontal CRS are mapped. Anything else is printed as PROJ wrote
# it rather than pluralized by a rule that would mangle it.
_UNIT_PLURALS = {
    "degree": "degrees", "metre": "metres", "meter": "meters",
    "kilometre": "kilometres", "foot": "feet", "US survey foot": "US survey feet",
    "grad": "grads", "link": "links",
}


# What a CRS costs you depends on the geometry, not on the CRS alone. A point
# has no area and a line has no area, so naming area functions there sends a
# reader after a measurement the data cannot produce. Each shape gets the
# measures it can actually compute, as the function name, what it returns, and
# the plural noun for the geodesic advice.
_MEASURES = {
    "polygon": ("distance and area", "{u} and square {u}", "distances and areas"),
    "line": ("length and distance", "{u}", "lengths and distances"),
    "point": ("distance", "{u}", "distances"),
}


def _vector_consequence(shape: str, unit: str, geographic: bool) -> str:
    """What the CRS means for SQL over a geometry column of this shape."""
    if shape not in _MEASURES:
        raise ValueError(
            f"a vector Collection using {{{{crs}}}} needs a known geometry to "
            f"say what follows from its CRS, got {shape!r}, expected one of "
            f"{', '.join(sorted(_MEASURES))}")
    names, returns, real = _MEASURES[shape]
    got = returns.format(u=unit)
    if geographic:
        return (f"Planar {names} functions return {got}, which are not ground "
                f"units and vary with latitude. For real {real} use a sphere "
                "or spheroid function, or transform to a projected CRS first.")
    return (f"Planar {names} functions return {got} directly, so no geodesic "
            "correction is needed. Web maps and anything joined to data in "
            "degrees need a transform to EPSG:4326 first.")


def _raster_consequence(unit: str, geographic: bool) -> str:
    """What the CRS means for a grid, which has no geometry column at all."""
    if geographic:
        return ("Pixel size is in degrees, so the ground size of a cell "
                "changes with latitude. Warp to a projected CRS before "
                "measuring anything off the grid.")
    return (f"Pixel size is in {unit}, so cell size and any distance read off "
            f"the grid are already in {unit}. Web maps need a warp to "
            "EPSG:3857, and joining to data in degrees needs EPSG:4326 first.")


def crs_block(crs: str, kind: str, geometry: str | None) -> list[str]:
    """The coordinate reference system block, and the consequence of it.

    The best-practices documentation page asks an AGENTS.md to name the CRS and
    say what follows from it, and the grader makes that an A-grade criterion.
    Every word here is computed from the `proj:code` the built `data` asset
    carries, the code, the CRS name, whether it is geographic or projected, and
    the axis unit, so a Collection that changes its output CRS cannot leave
    stale prose behind. Nothing about the CRS is written by hand in a manifest.

    The consequence is chosen by kind and geometry as well, because the same
    CRS costs a different thing on each. A polygon layer can measure area, a
    line layer length, a point layer only distance, and a raster has no
    geometry column to run any of them over, so it is told about pixel size
    instead. Naming a measure the data cannot produce reads as authoritative
    and sends a consumer down a dead end.

    A Collection with no CRS never gets this block, and `{{crs}}` is withheld
    from its templates rather than rendering something vague."""
    d = describe_crs(crs)
    unit = _UNIT_PLURALS.get(d["unit"], d["unit"])
    geographic = d["kind"] == "geographic"
    return [
        "## Coordinate Reference System",
        "",
        f"{d['code']}, {d['name']}, a {d['kind']} coordinate reference system "
        f"whose coordinates are in {unit}.",
        _raster_consequence(unit, geographic) if kind == "raster"
        else _vector_consequence(geometry or "", unit, geographic),
        "The `data` asset carries the same code as `proj:code`.",
    ]


def provenance_block(spec: dict, providers: list[dict], facts: dict) -> list[str]:
    """The license and provenance block core.md requires in every README."""
    src = facts["src"]
    attribution = spec.get("attribution")
    lines = [
        "## Provenance and License",
        "",
        f"License, {spec['license']}."
        + (f" Attribution, {attribution}." if attribution else ""),
        f"Providers, {_providers_sentence(providers)}.",
        f"Original source, {src['url']} .",
    ]
    kind = facts["kind"]
    if kind == "vector":
        lines.append(f"Features, {facts['n']:,}. Cloud-native asset, "
                     f"{facts['data_name']} (GeoParquet 2.0).")
    elif kind == "raster":
        lines.append(f"Bands, {len(facts['bands'])}. CRS, {facts['crs']}. "
                     f"Cloud-native asset, {facts['data_name']} (COG).")
    else:
        lines.append(f"Rows, {facts['n']:,}. Columns, {len(facts['cols'])}. "
                     f"Cloud-native asset, {facts['data_name']} (Parquet).")
        aoi = facts.get("aoi")
        lines.append("Non-geospatial table, the bounding box is the area of "
                     "interest the data pertains to"
                     + (f", {aoi}." if aoi else " and defaults to the whole world."))
    if not src.get("stable", True):
        lines.append("The upstream source is a live endpoint, so it is referenced "
                     "by URL only and not archived as a source asset.")
    return lines


# Doc templates in the manifest are markdown with {{placeholder}} lines. Each
# placeholder expands to a block the generator computes from the built assets,
# so the numbers, schema tables, and open-it code in the docs cannot drift from
# the catalog they describe. A placeholder the surface does not offer is an
# error, a typo would otherwise publish literally.
DOC_PLACEHOLDER = re.compile(r"^\{\{([a-z_]+)\}\}$")


def render_template(template: str, blocks: dict[str, list[str]], where: str) -> list[str]:
    out: list[str] = []
    for raw in template.strip("\n").rstrip().splitlines():
        m = DOC_PLACEHOLDER.match(raw.strip())
        if not m:
            out.append(raw)
            continue
        name = m.group(1)
        if name not in blocks:
            # Two cases land here, a typo and a placeholder this Collection has
            # nothing to fill. Both are build failures, and the message names
            # the second because it is the one that looks like a bug.
            raise ValueError(
                f"{where} uses {{{{{name}}}}}, which is not available here, "
                f"available are {sorted(blocks)}. A placeholder is withheld "
                "when the Collection cannot fill it, for example {{crs}} on a "
                "Collection whose data asset carries no proj:code.")
        out.extend(blocks[name])
    return out


def _first_sentence(text: str) -> str:
    t = " ".join(text.strip().split())
    m = re.match(r"(.+?\.)(\s|$)", t)
    return m.group(1) if m else t


def blurb(spec: dict) -> str:
    """One line for catalog collection tables, authored or first sentence."""
    return spec.get("blurb") or _first_sentence(spec["description"])


def collection_readme_extra(spec: dict, facts: dict) -> list[str]:
    """Everything after the title and description in a collection README.

    A manifest `docs.readme` template drives the structure, so each collection
    reads differently while the generated blocks keep the facts honest. Without
    a template the default skeleton is emitted. The provenance block core.md
    requires is appended whenever the template does not place it itself."""
    docs = spec.get("docs") or {}
    blocks = {
        "quickstart": quickstart_block(facts["kind"], facts["data_name"]),
        "schema": schema_block(facts["cols"]),
        "provenance": provenance_block(spec, facts["providers"], facts),
        "join": join_section(facts.get("join") or {}),
    }
    if facts.get("crs"):
        blocks["crs"] = crs_block(facts["crs"], facts["kind"],
                                  spec.get("geometry"))
    template = (docs.get("readme") or "").strip()
    if not template:
        template = "## Quick Start\n\n{{quickstart}}"
        if schema_block(facts["cols"]):
            template += "\n\n## Schema\n\n{{schema}}"
        if facts.get("join"):
            template += "\n\n{{join}}"
        template += "\n\n{{provenance}}"
    lines = render_template(template, blocks, f"{spec['id']} docs.readme")
    if "## Provenance and License" not in lines:
        lines += [""] + blocks["provenance"]
    return lines


def collection_agents_lines(spec: dict, facts: dict) -> list[str]:
    """The body of a collection AGENTS.md.

    A manifest `docs.agents` template carries the dataset-specific guidance,
    join keys, quirks, and tested queries. The generated access block is
    available as {{access}} and the generated coordinate reference system block
    as {{crs}}, the latter only where the data asset carries a `proj:code`.
    Without a template a minimal fallback is emitted so a bare manifest still
    builds a conformant catalog."""
    docs = spec.get("docs") or {}
    access = access_line(facts["kind"], facts["data_name"],
                         facts["has_visual"], facts["has_thumb"])
    blocks = {"access": [access]}
    if facts.get("crs"):
        blocks["crs"] = crs_block(facts["crs"], facts["kind"],
                                  spec.get("geometry"))
    template = (docs.get("agents") or "").strip()
    if not template:
        src = facts["src"]
        lines = [f"This collection holds {spec['title']}.", access,
                 f"License is {spec['license']}."]
        lines.append(
            f"The original upstream source is {src['url']} , "
            + ("tagged on the source-role asset." if src.get("stable", True)
               else "a live endpoint referenced by URL only."))
        join = facts.get("join")
        if join:
            lines.append(
                f"This table has no geometry. Join column {join['column']} to "
                f"{join['target']} on {join['target_column']} to map it, see the README.")
        return lines
    return render_template(template, blocks, f"{spec['id']} docs.agents")


def readme_md(title: str, description: str, extra_lines: list[str]) -> str:
    body = [f"# {title}", "", description.strip(), ""]
    body += extra_lines
    body.append("")
    return "\n".join(body)


def agents_md(title: str, guidance: list[str]) -> str:
    body = [f"# Agent Guidance, {title}", ""]
    body += guidance
    body.append("")
    return "\n".join(body)


def write_sidecars(node_dir: Path, title: str, description: str,
                   readme_extra: list[str], agents_lines: list[str]) -> None:
    (node_dir / "README.md").write_text(readme_md(title, description, readme_extra))
    (node_dir / "AGENTS.md").write_text(agents_md(title, agents_lines))


SIDE_LINKS = [
    link("agents", "./AGENTS.md", "text/markdown", "Guidance for AI agents"),
    link("describedby", "./README.md", "text/markdown", "Human-readable documentation"),
]


def write_logo(manifest: dict, out: Path) -> dict | None:
    """Copy the catalog logo into `_assets/` and return its `icon` link.

    core.md scopes the logo to the root catalog and asks for a relative href, so
    the image is copied beside the catalog rather than linked where it lives.
    That keeps the built tree portable, and it keeps the link resolvable, which
    the spec requires of every link in a catalog.

    A manifest without a `logo` block builds a catalog without one. A logo whose
    media type no browser renders is a manifest error, not a silent omission,
    because the link would validate and then show nothing.
    """
    logo = manifest.get("logo")
    if not logo:
        return None
    src = Path(logo["path"])
    if not src.is_file():
        raise ValueError(f"logo source not found: {src}")
    if logo["type"] not in ICON_TYPES:
        raise ValueError(
            f"logo type {logo['type']!r} is not one a browser renders, "
            f"expected one of {sorted(ICON_TYPES)}")
    assets = out / "_assets"
    assets.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, assets / src.name)
    return link("icon", f"./_assets/{src.name}", logo["type"], logo.get("title"))


# ------------------------------------------------------------- collection build
def build_collection(spec: dict, host: dict, out_root: Path, cache: Path,
                     thumb: dict, manifest_output_crs: str | None) -> dict:
    cid = spec["id"]
    seg = cid.split("/")
    depth = len(seg)
    coll_dir = out_root.joinpath(*seg)
    if coll_dir.exists():
        shutil.rmtree(coll_dir)
    coll_dir.mkdir(parents=True, exist_ok=True)
    stem = seg[-1]
    kind = spec["kind"]
    providers, is_mirror = resolve_providers(spec, host)
    check_provenance(spec, is_mirror)
    prov = spec.get("provenance", {}) or {}
    src = spec["source"]
    out_crs = resolve_output_crs(spec, manifest_output_crs)

    print(f"[{cid}] fetch + convert ({kind})", file=sys.stderr)
    local = fetch(src["url"], cache, stable=src.get("stable", True))

    exts = [SCHEMA_URI, FILE_EXT]
    assets: dict[str, dict] = {}
    links: list[dict] = []
    layer_name = stem
    deriv = spec.get("derivatives", {}) or {}
    data_name = ""
    # The table extension scopes `table:*` to Collection fields and Item
    # Properties, and PORTO-FMT-046 asks a vector collection for them there, so
    # these are merged into the collection rather than onto the data asset.
    table_fields: dict[str, Any] = {}

    if kind in ("vector",):
        data_pq = coll_dir / f"{stem}.parquet"
        data_name = data_pq.name
        bbox, n, norm, canon_crs = to_geoparquet(local, src, data_pq, out_crs)
        cols = describe_columns(table_columns(data_pq), spec.get("columns") or {})
        geom_col = next((c["name"] for c in cols if c["type"] == "geometry"), "geom")
        assets["data"] = asset(data_pq, MEDIA["geoparquet"], ["data"],
                               f"{spec['title']} (GeoParquet)",
                               {"proj:code": canon_crs})
        table_fields = {"table:columns": cols, "table:primary_geometry": geom_col,
                        "table:row_count": n}
        exts += [TABLE_EXT, PROJ_EXT]
        add_source_asset(assets, local, src)
        source_url = f"../{stem}.parquet"
        if deriv.get("pmtiles"):
            pm = coll_dir / f"{stem}.pmtiles"
            make_pmtiles(norm, pm, layer_name)
            assets["visual"] = asset(pm, MEDIA["pmtiles"], ["visual"], f"{spec['title']} (PMTiles)")
            exts.append(WEBMAP_EXT)
            links.append(link("pmtiles", f"./{pm.name}", MEDIA["pmtiles"], "Web map tiles",
                              {"pmtiles:layers": [layer_name]}))
            source_url = f"../{pm.name}"
        # Styles read the PMTiles where a visual exists, and the GeoParquet
        # itself where the collection renders from source, which clients like
        # portolan-browser bind onto the data they loaded. The first variant
        # also carries the default role, so the default is discoverable without
        # relying on asset order, which a JSON object does not guarantee.
        # core.md requires exactly that once a Collection has more than one
        # style.
        if (spec.get("style") or {}).get("variants"):
            add_style_assets(assets, coll_dir, layer_name, source_url, norm, spec)
        if deriv.get("thumbnail", True):
            th = coll_dir / "thumbnail.png"
            tbbox = spec.get("thumbnail_bbox") or bbox
            make_thumbnail_vector(norm, th, tbbox, thumb_style(spec), thumb)
            assets["thumbnail"] = asset(th, MEDIA["png"], ["thumbnail"], _thumb_desc(thumb))
        bands, code = [], canon_crs
        norm.unlink(missing_ok=True)

    elif kind == "raster":
        cog = coll_dir / f"{stem}.tif"
        data_name = cog.name
        code = to_cog(local, cog, out_crs)
        bands = bands_from_cog(cog)
        bbox = bbox_wgs84_raster(cog)
        n = 0
        assets["data"] = asset(cog, MEDIA["cog"], ["data"], f"{spec['title']} (COG)",
                               {"bands": bands, "proj:code": code})
        add_source_asset(assets, local, src)
        # Band statistics live in STAC 1.1 core `bands`. The raster extension v2.0.0
        # schema conflicts with collection-level assets (spec issues #52 / #41), so
        # it is not declared here, projection carries the CRS.
        exts += [PROJ_EXT]
        if deriv.get("thumbnail", True):
            th = coll_dir / "thumbnail.png"
            tbbox = spec.get("thumbnail_bbox") or bbox
            make_thumbnail_raster(cog, th, tbbox, thumb)
            assets["thumbnail"] = asset(th, MEDIA["png"], ["thumbnail"], _thumb_desc(thumb))
        cols = []

    elif kind == "tabular":
        data_pq = coll_dir / f"{stem}.parquet"
        data_name = data_pq.name
        to_table_parquet(local, data_pq)
        cols = describe_columns(table_columns(data_pq), spec.get("columns") or {})
        n = feature_count(data_pq)
        bbox = None
        assets["data"] = asset(data_pq, MEDIA["parquet"], ["data"],
                               f"{spec['title']} (Parquet)")
        table_fields = {"table:columns": cols, "table:row_count": n}
        add_source_asset(assets, local, src)
        exts.append(TABLE_EXT)
        bands, code = [], None
    else:
        raise ValueError(f"unknown kind {kind}")

    add_metadata_asset(assets, spec, coll_dir, cache)

    # structural + provenance links
    root_href = "../" * depth + "catalog.json"
    parent_href = "../catalog.json"
    links = ([link("root", root_href, "application/json"),
              link("parent", parent_href, "application/json")]
             + links)
    if is_mirror and prov.get("via"):
        links.append(link("via", prov["via"], "text/html", "Original source"))
    if prov.get("canonical"):
        links.append(link("canonical", prov["canonical"], "application/json",
                          "Upstream metadata record"))
    links += license_links(spec)
    links += [dict(SIDE_LINKS[0]), dict(SIDE_LINKS[1])]

    if spec.get("attribution"):
        exts.append(ATTRIBUTION_EXT)

    extent: dict[str, Any] = {}
    if bbox is not None:
        extent["spatial"] = {"bbox": [bbox]}
    else:
        # A tabular collection has no geometry, but core.md still asks its bbox to
        # be the area of interest the data pertains to rather than a footprint. A
        # manifest `bbox` states that area, the whole world is only the fallback
        # for a genuinely global table.
        extent["spatial"] = {"bbox": [spec.get("bbox") or [-180, -90, 180, 90]]}
    temporal = spec.get("temporal")
    if temporal:
        extent["temporal"] = {"interval": [temporal]}

    coll: dict[str, Any] = {
        "type": "Collection",
        "stac_version": STAC_VERSION,
        "stac_extensions": exts,
        # core.md, "a nested collection's ID is its POSIX path from the catalog
        # root", so the id is the full manifest id, not just the leaf segment.
        # Filenames still use the leaf, a slash cannot appear in a filename.
        "id": cid,
        "title": spec["title"],
        "description": spec["description"].strip(),
        "license": spec["license"],
        "keywords": spec.get("keywords", []),
        "providers": providers,
        "extent": extent,
        **table_fields,
        "assets": assets,
        "links": links,
    }
    if spec.get("attribution"):
        coll["attribution"] = spec["attribution"]
    if prov.get("updated"):
        coll["updated"] = prov["updated"]

    (coll_dir / "collection.json").write_text(json.dumps(coll, ensure_ascii=False, indent=2) + "\n")

    # sidecars, structure and prose from the manifest docs templates
    join = dict(spec.get("join") or {})
    if join:
        join["this_file"] = data_name
    facts = {
        "kind": kind, "data_name": data_name, "n": n, "cols": cols,
        "bands": bands, "crs": code, "aoi": spec.get("bbox"),
        "has_visual": bool(assets.get("visual")),
        "has_thumb": bool(assets.get("thumbnail")),
        "src": src, "providers": providers, "join": join,
    }
    write_sidecars(coll_dir, spec["title"], spec["description"].strip(),
                   collection_readme_extra(spec, facts),
                   collection_agents_lines(spec, facts))

    return {"id": cid, "seg": seg, "title": spec["title"], "updated": prov.get("updated"),
            "license": spec["license"], "is_mirror": is_mirror, "source": src["url"],
            "source_title": src["title"], "stable": src.get("stable", True),
            "kind": kind, "geometry": spec.get("geometry"), "n": n,
            "bands": len(bands), "blurb": blurb(spec)}


# ------------------------------------------------------------- styles-only regen
def regen_styles(manifest: dict, out: Path) -> None:
    """Re-author every style variant against the committed tree, touching only
    styles/*.json and each collection.json's style assets.

    Styles iterate far more often than data, and a full rebuild refetches the
    live upstream endpoints, churning parquet, PMTiles, and checksums under a
    paint change. Values are sampled from the committed GeoParquet, attributes
    only, so the CRS does not matter. Thumbnails are not re-rendered, which is
    safe exactly when the default variant's paint is unchanged, and the full CI
    rebuild repaints them from the same manifest either way."""
    for spec in manifest["collections"]:
        if spec.get("kind") != "vector" or not (spec.get("style") or {}).get("variants"):
            continue
        seg = spec["id"].split("/")
        coll_dir = out.joinpath(*seg)
        coll_path = coll_dir / "collection.json"
        coll = json.loads(coll_path.read_text())
        stem = seg[-1]
        source_url = (f"../{stem}.pmtiles" if "visual" in coll["assets"]
                      else f"../{stem}.parquet")
        add_style_assets(coll["assets"], coll_dir, stem, source_url,
                         coll_dir / f"{stem}.parquet", spec)
        coll_path.write_text(json.dumps(coll, ensure_ascii=False, indent=2) + "\n")
        print(f"[{spec['id']}] styles re-authored", file=sys.stderr)


# --------------------------------------------------------------- catalog build
def _contents_label(c: dict) -> str:
    """Feature count and geometry in one cell, per the best-practices table."""
    if c["kind"] == "vector":
        return f"{c['n']:,} {c.get('geometry') or 'feature'}s"
    if c["kind"] == "raster":
        return f"{c['bands']}-band raster"
    return f"{c['n']:,} rows"


def collections_table(colls: list[dict], nested: bool) -> list[str]:
    """The table of contents the best-practices page asks catalog READMEs to be,
    title, feature count and geometry, one-line description. `nested` links
    through the group directory for the root catalog."""
    lines = ["| Collection | Contents | Description |", "|---|---|---|"]
    for c in colls:
        path = "/".join(c["seg"]) if nested else c["seg"][-1]
        lines.append(f"| [{c['title']}](./{path}/README.md) "
                     f"| {_contents_label(c)} | {c['blurb']} |")
    return lines


def _provenance_sentence(colls: list[dict]) -> str:
    """Whether the Collections beneath this node are mirrors, in one sentence."""
    n = len(colls)
    mirrors = sum(1 for c in colls if c["is_mirror"])
    official = n - mirrors
    if not official:
        if n == 1:
            return ("The Collection here is a mirror, so this catalog hosts a "
                    "copy of data produced elsewhere.")
        return (f"All {n} Collections here are mirrors, so this catalog hosts "
                "copies of data produced elsewhere.")
    if not mirrors:
        subject = ("The Collection here is published" if n == 1
                   else f"All {n} Collections here are published")
        return f"{subject} by the organization that produced the data."
    return (f"{mirrors} of the {n} Collections here are mirrors of data produced "
            f"elsewhere, and {official} come straight from the organization that "
            "produced them.")


def _source_sentence(c: dict) -> str:
    """One Collection and its upstream file, named and linked inside a sentence."""
    src = f"[{c['source_title']}]({c['source']})"
    if c["stable"]:
        return (f"{c['title']} is built from the {src}, pinned by checksum and "
                f"licensed {c['license']}.")
    return (f"{c['title']} tracks the {src}, a live endpoint refetched on every "
            f"build rather than pinned, licensed {c['license']}.")


def sources_block(colls: list[dict]) -> list[str]:
    """Licensing and provenance for a catalog-level README, written as prose.

    core.md requires every README, on catalogs as well as collections, to carry a
    title, a description, a license, and data provenance. A catalog holds no data
    of its own, so it states the licenses and the provenance of what it contains.

    best-practices/documentation.md asks for every link to be introduced in a
    flowing sentence rather than collected in a bare reference list at the
    bottom, so each Collection gets one sentence naming the upstream file it was
    built from, whether those bytes are pinned, and the license they arrive
    under. Sentences run three to a paragraph, which keeps a group of one and a
    catalog of eight both readable. One sentence per source line keeps a diff
    pointed at the Collection that changed, and markdown reads consecutive lines
    as one paragraph anyway."""
    if not colls:
        return []
    lines = [_provenance_sentence(colls)]
    sentences = [_source_sentence(c) for c in colls]
    for i in range(0, len(sentences), 3):
        lines += [""] + sentences[i:i + 3]
    return lines


def agents_index(colls: list[dict], nested: bool) -> list[str]:
    """Child pointers for a catalog-level AGENTS.md, each with its own guide."""
    lines = []
    for c in colls:
        path = "/".join(c["seg"]) if nested else c["seg"][-1]
        lines.append(f"- {c['title']}, {_contents_label(c)}, guide at "
                     f"./{path}/AGENTS.md")
    return lines


def catalog_sidecar_bodies(title: str, description: str, colls: list[dict],
                           nested: bool, templates: dict,
                           where: str) -> tuple[list[str], list[str]]:
    """README and AGENTS bodies for a catalog node, template-driven like the
    collections, with {{collections}}, {{sources}}, and {{agents_index}} blocks."""
    blocks = {
        "collections": collections_table(colls, nested),
        "sources": sources_block(colls),
        "agents_index": agents_index(colls, nested),
    }
    readme_tpl = (templates.get("readme") or "").strip() or (
        "## Collections\n\n{{collections}}\n\n"
        "## Where the Data Comes From\n\n{{sources}}")
    readme = render_template(readme_tpl, blocks, f"{where} readme")
    # core.md wants the license and provenance on every README, so a template
    # that leaves out {{sources}} gets the block appended anyway. Tested on the
    # template rather than on the rendered prose, which has no fixed phrase to
    # match now that the block is written as sentences.
    if "{{sources}}" not in readme_tpl:
        readme += [""] + sources_block(colls)
    agents_tpl = (templates.get("agents") or "").strip() or (
        f"This catalog groups {len(colls)} Collections. Each carries its own "
        "AGENTS.md with join keys, quirks, and tested queries, so follow the "
        "per-collection guides below.\n\n{{agents_index}}")
    agents = render_template(agents_tpl, blocks, f"{where} agents")
    return readme, agents


def _group_meta(manifest: dict, seg: str) -> tuple[str, str]:
    entry = (manifest.get("catalogs", {}) or {}).get(seg)
    if entry:
        return entry["title"], entry["description"].strip()
    return seg.title(), f"{seg} Collections."


# PORTO-CORE-013, "Collection IDs SHOULD contain only lowercase letters,
# numbers, hyphens, and underscores, start with a letter, and be unique within
# the catalog." Enforced as an error here rather than left to rashid, because
# every one of these becomes a directory name and an href before any validator
# sees the tree.
ID_SEGMENT = re.compile(r"^[a-z][a-z0-9_-]*$")


def check_collection_ids(specs: list[dict]) -> None:
    """Reject collection ids that would build a broken or unsafe tree.

    Each id is split on `/` into a group segment and a collection segment, and
    the whole generator assumes exactly that shape. One segment puts a
    Collection and its group Catalog in the same directory, where the sidecars
    of one overwrite the other. Three or more leaves the parent link pointing at
    a catalog that is never written. Neither is caught downstream, both produce
    a tree that validates field by field while its links go nowhere.

    Uniqueness matters more than it looks. `build_collection` rmtree's the
    target directory first, so a duplicate id silently deletes the earlier
    build and leaves the group catalog carrying the same child link twice.
    """
    seen: dict[str, int] = {}
    errors: list[str] = []
    for index, spec in enumerate(specs):
        cid = str(spec.get("id", ""))
        if cid in seen:
            errors.append(
                f"collection[{index}] id {cid!r} duplicates collection[{seen[cid]}], "
                "the second build would delete the first"
            )
        seen.setdefault(cid, index)
        segments = cid.split("/")
        if len(segments) != 2:
            errors.append(
                f"collection[{index}] id {cid!r} has {len(segments)} segment(s), "
                "ids are '<catalog>/<collection>'"
            )
        for segment in segments:
            if not ID_SEGMENT.match(segment):
                errors.append(
                    f"collection[{index}] id {cid!r} has segment {segment!r}, "
                    "which is not lowercase letters, numbers, hyphens, and "
                    "underscores starting with a letter"
                )
    if errors:
        raise SystemExit(
            f"{len(errors)} collection id error(s):\n"
            + "\n".join(f"  - {err}" for err in errors)
        )


def build_catalog(manifest: dict, out: Path, cache: Path, only: str | None) -> None:
    # Validated against the whole manifest, never the --only subset, so a broken
    # id cannot hide behind a filtered build.
    check_collection_ids(manifest["collections"])
    out.mkdir(parents=True, exist_ok=True)
    thumb = build_thumb_ctx(manifest, cache)
    specs = manifest["collections"]
    if only:
        specs = [s for s in specs if s["id"] == only]
        assert specs, f"no collection with id {only}"
    mcrs = manifest.get("output_crs")
    built = [build_collection(s, manifest["host"], out, cache, thumb, mcrs) for s in specs]

    # group -> collections
    groups: dict[str, list[dict]] = {}
    for b in built:
        groups.setdefault(b["seg"][0], []).append(b)

    updates = [b["updated"] for b in built if b.get("updated")]
    catalog_updated = max(updates) if updates else None

    # Intermediate (nested) catalogs, titles come from the manifest. Skipped
    # under --only for the same reason the root below is. `groups` is built from
    # the filtered list, so rewriting one here would drop every sibling
    # Collection from its child links while leaving them on disk, unreachable.
    # --only also skips validation, so nothing downstream would catch it, and a
    # committed rebuild now publishes.
    for gseg, colls in ({} if only else groups).items():
        gdir = out / gseg
        gdir.mkdir(parents=True, exist_ok=True)
        gtitle, gdesc = _group_meta(manifest, gseg)
        children = [link("child", f"./{c['seg'][-1]}/collection.json", "application/json", c["title"])
                    for c in colls]
        cat = {
            "type": "Catalog", "stac_version": STAC_VERSION, "stac_extensions": [SCHEMA_URI],
            "id": gseg, "title": gtitle, "description": gdesc,
            "links": ([link("root", "../catalog.json", "application/json"),
                       link("parent", "../catalog.json", "application/json")]
                      + children + [dict(SIDE_LINKS[0]), dict(SIDE_LINKS[1])]),
        }
        # A synced catalog carries `updated` too, not just the collections beneath
        # it, so freshness can be judged at any level of the tree.
        gupdates = [c["updated"] for c in colls if c.get("updated")]
        if gupdates:
            cat["updated"] = max(gupdates)
        (gdir / "catalog.json").write_text(json.dumps(cat, ensure_ascii=False, indent=2) + "\n")
        templates = (manifest.get("catalogs", {}) or {}).get(gseg, {}) or {}
        readme, agents = catalog_sidecar_bodies(
            gtitle, gdesc, colls, nested=False, templates=templates,
            where=f"catalogs.{gseg}")
        write_sidecars(gdir, gtitle, gdesc, readme, agents)

    # root catalog (only rebuild fully when not filtering to one collection)
    if not only:
        root_children = [
            link("child", f"./{g}/catalog.json", "application/json", _group_meta(manifest, g)[0])
            for g in groups
        ]
        # The logo is a root-catalog link, so it is emitted here and nowhere else.
        icon = write_logo(manifest, out)
        root = {
            "type": "Catalog", "stac_version": STAC_VERSION, "stac_extensions": [SCHEMA_URI],
            "id": manifest["id"], "title": manifest["title"],
            "description": manifest["description"].strip(),
            "links": ([link("root", "./catalog.json", "application/json")]
                      + root_children + [dict(SIDE_LINKS[0]), dict(SIDE_LINKS[1])]
                      + ([icon] if icon else [])),
        }
        if catalog_updated:
            root["updated"] = catalog_updated
        (out / "catalog.json").write_text(json.dumps(root, ensure_ascii=False, indent=2) + "\n")
        readme, agents = catalog_sidecar_bodies(
            manifest["title"], manifest["description"].strip(), built,
            nested=True, templates=manifest.get("docs") or {}, where="docs")
        write_sidecars(out, manifest["title"], manifest["description"].strip(),
                       readme, agents)


# --------------------------------------------------------------- docs-only regen
def _facts_from_collection(spec: dict, coll: dict) -> dict:
    """Rebuild the sidecar facts from a committed collection.json."""
    assets = coll["assets"]
    data = assets["data"]
    data_name = data["href"].removeprefix("./")
    cols = describe_columns(coll.get("table:columns", []), spec.get("columns") or {})
    join = dict(spec.get("join") or {})
    if join:
        join["this_file"] = data_name
    return {
        "kind": spec["kind"], "data_name": data_name,
        "n": coll.get("table:row_count", 0), "cols": cols,
        "bands": data.get("bands", []), "crs": data.get("proj:code"),
        "aoi": spec.get("bbox"),
        "has_visual": "visual" in assets, "has_thumb": "thumbnail" in assets,
        "src": spec["source"], "providers": coll["providers"], "join": join,
    }


def regen_docs(manifest: dict, out: Path, cache: Path) -> None:
    """Regenerate every README.md and AGENTS.md from the manifest against the
    already-built tree, no fetch, no conversion.

    Documentation iterates far more often than data, and a full rebuild refetches
    the live upstream endpoints, churning binary assets under a prose change.
    This path reads each committed collection.json for the built facts. It also
    merges the manifest column descriptions back into `table:columns` and
    refreshes the identity fields the manifest owns, so the metadata surface the
    docs generate from cannot drift from the manifest that generated the docs."""
    check_collection_ids(manifest["collections"])
    built = []
    for spec in manifest["collections"]:
        seg = spec["id"].split("/")
        coll_dir = out.joinpath(*seg)
        coll_path = coll_dir / "collection.json"
        coll = json.loads(coll_path.read_text())
        if coll.get("table:columns"):
            coll["table:columns"] = describe_columns(
                coll["table:columns"], spec.get("columns") or {})
        coll["title"] = spec["title"]
        coll["description"] = spec["description"].strip()
        coll["license"] = spec["license"]
        coll["keywords"] = spec.get("keywords", [])
        if spec.get("temporal"):
            coll.setdefault("extent", {})["temporal"] = {"interval": [spec["temporal"]]}
        add_metadata_asset(coll["assets"], spec, coll_dir, cache)
        coll_path.write_text(json.dumps(coll, ensure_ascii=False, indent=2) + "\n")
        facts = _facts_from_collection(spec, coll)
        write_sidecars(coll_dir, spec["title"], spec["description"].strip(),
                       collection_readme_extra(spec, facts),
                       collection_agents_lines(spec, facts))
        _, is_mirror = resolve_providers(spec, manifest["host"])
        prov = spec.get("provenance", {}) or {}
        built.append({"id": spec["id"], "seg": seg, "title": spec["title"],
                      "updated": prov.get("updated"), "license": spec["license"],
                      "is_mirror": is_mirror, "source": spec["source"]["url"],
                      "source_title": spec["source"]["title"],
                      "stable": spec["source"].get("stable", True),
                      "kind": spec["kind"], "geometry": spec.get("geometry"),
                      "n": facts["n"], "bands": len(facts["bands"]),
                      "blurb": blurb(spec)})
    groups: dict[str, list[dict]] = {}
    for b in built:
        groups.setdefault(b["seg"][0], []).append(b)
    for gseg, colls in groups.items():
        gtitle, gdesc = _group_meta(manifest, gseg)
        templates = (manifest.get("catalogs", {}) or {}).get(gseg, {}) or {}
        readme, agents = catalog_sidecar_bodies(
            gtitle, gdesc, colls, nested=False, templates=templates,
            where=f"catalogs.{gseg}")
        write_sidecars(out / gseg, gtitle, gdesc, readme, agents)
    readme, agents = catalog_sidecar_bodies(
        manifest["title"], manifest["description"].strip(), built,
        nested=True, templates=manifest.get("docs") or {}, where="docs")
    write_sidecars(out, manifest["title"], manifest["description"].strip(),
                   readme, agents)
