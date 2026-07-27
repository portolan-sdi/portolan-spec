"""STAC assembly, manifest, providers, assets, links, sidecars, and the
collection and catalog builders.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import yaml

from common import filesize, multihash
from config import (
    SCHEMA_URI, FILE_EXT, WEBMAP_EXT, TABLE_EXT, PROJ_EXT,
    ATTRIBUTION_EXT, STAC_VERSION, MEDIA,
)
from fetch import fetch
from crs import resolve_output_crs
from convert import (
    to_geoparquet, feature_count, to_cog, bands_from_cog,
    bbox_wgs84_raster, to_table_parquet, table_columns,
)
from derivatives import make_pmtiles, author_styles
from thumbnails import (
    make_thumbnail_vector, make_thumbnail_raster, build_thumb_ctx, _thumb_desc,
)


# --------------------------------------------------------------------- manifest
def load_manifest(path: Path) -> dict:
    m = yaml.safe_load(path.read_text())
    assert m["schema_uri"] == SCHEMA_URI, "manifest schema_uri must be the pinned v0.1.0 URI"
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


def style_asset(path: Path, variant: str) -> dict:
    return {"href": f"./styles/{path.name}", "type": MEDIA["style"],
            "title": f"{variant.capitalize()} MapLibre style", "roles": ["style"],
            "file:size": filesize(path), "file:checksum": multihash(path)}


def source_asset(local: Path, spec_source: dict) -> dict:
    return {"href": spec_source["url"], "type": spec_source["media_type"],
            "title": spec_source["title"], "roles": ["data", "source"],
            "file:size": filesize(local), "file:checksum": multihash(local)}


# --------------------------------------------------------------- prose sidecars
def _providers_sentence(providers: list[dict]) -> str:
    parts = [f"{p['name']} ({', '.join(p.get('roles', []))})" for p in providers]
    return ", ".join(parts)


def open_snippet(kind: str, data_name: str) -> tuple[list[str], str]:
    """Return (readme_markdown_lines, agents_line) with runnable code for opening
    the cloud-native data asset, chosen by kind. The README block shows a couple
    of common tools, the agents line names the one an agent should reach for."""
    if kind == "vector":
        lines = [
            "## Open the data",
            "",
            "The `data` asset is GeoParquet 2.0 with a native geometry type and a "
            "covering bbox column for fast web-client pruning. Read it with a recent "
            "GeoPandas built on pyarrow 24 or newer.",
            "",
            "```python",
            "import geopandas as gpd",
            "",
            f'gdf = gpd.read_parquet("{data_name}")',
            "print(gdf.head())",
            "```",
            "",
            "Or query it in place with a recent DuckDB spatial.",
            "",
            "```sql",
            "INSTALL spatial; LOAD spatial;",
            f"SELECT * FROM read_parquet('{data_name}') LIMIT 5;",
            "```",
        ]
        agents = f'Read the GeoParquet `data` asset with GeoPandas, gpd.read_parquet("{data_name}").'
        return lines, agents
    if kind == "raster":
        lines = [
            "## Open the data",
            "",
            "The `data` asset is a Cloud Optimized GeoTIFF. Open it as an xarray "
            "array with rioxarray.",
            "",
            "```python",
            "import rioxarray",
            "",
            f'da = rioxarray.open_rasterio("{data_name}", masked=True)',
            "print(da)",
            "```",
            "",
            "Or read bands and metadata with rasterio.",
            "",
            "```python",
            "import rasterio",
            "",
            f'with rasterio.open("{data_name}") as src:',
            "    print(src.profile)",
            "    band1 = src.read(1)",
            "```",
        ]
        agents = f'Read the COG `data` asset with rioxarray.open_rasterio("{data_name}") for xarray, or rasterio.'
        return lines, agents
    # tabular
    lines = [
        "## Open the data",
        "",
        "The `data` asset is Parquet. Open it with pandas.",
        "",
        "```python",
        "import pandas as pd",
        "",
        f'df = pd.read_parquet("{data_name}")',
        "print(df.head())",
        "```",
        "",
        "Or query it in place with DuckDB.",
        "",
        "```sql",
        f"SELECT * FROM read_parquet('{data_name}') LIMIT 5;",
        "```",
    ]
    agents = f'Read the Parquet `data` asset with pandas, pd.read_parquet("{data_name}").'
    return lines, agents


def readme_md(title: str, description: str, extra_lines: list[str]) -> str:
    body = [f"# {title}", "", description.strip(), ""]
    body += extra_lines
    body.append("")
    return "\n".join(body)


def agents_md(title: str, guidance: list[str]) -> str:
    body = [f"# Agent guidance, {title}", ""]
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


# ------------------------------------------------------------- collection build
def build_collection(spec: dict, host: dict, out_root: Path, cache: Path,
                     thumb: dict, manifest_output_crs: str | None) -> dict:
    cid = spec["id"]
    seg = cid.split("/")
    depth = len(seg)
    coll_dir = out_root.joinpath(*seg)
    if coll_dir.exists():
        import shutil
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

    if kind in ("vector",):
        data_pq = coll_dir / f"{stem}.parquet"
        data_name = data_pq.name
        bbox, n, norm, canon_crs = to_geoparquet(local, src, data_pq, out_crs)
        cols = table_columns(data_pq)
        geom_col = next((c["name"] for c in cols if c["type"] == "geometry"), "geom")
        assets["data"] = asset(data_pq, MEDIA["geoparquet"], ["data"],
                               f"{spec['title']} (GeoParquet)",
                               {"table:columns": cols, "table:primary_geometry": geom_col,
                                "table:row_count": n, "proj:code": canon_crs})
        exts += [TABLE_EXT, PROJ_EXT]
        assets["source"] = source_asset(local, src)
        if deriv.get("pmtiles"):
            pm = coll_dir / f"{stem}.pmtiles"
            make_pmtiles(norm, pm, layer_name)
            assets["visual"] = asset(pm, MEDIA["pmtiles"], ["visual"], f"{spec['title']} (PMTiles)")
            exts.append(WEBMAP_EXT)
            links.append(link("pmtiles", f"./{pm.name}", MEDIA["pmtiles"], "Web map tiles",
                              {"pmtiles:layers": [layer_name]}))
            # styles read the PMTiles, so only author them where a visual exists
            for sp in author_styles(coll_dir / "styles", layer_name, pm.name, norm, spec):
                assets[f"style-{sp.stem}"] = style_asset(sp, sp.stem)
        if deriv.get("thumbnail", True):
            th = coll_dir / "thumbnail.png"
            tbbox = spec.get("thumbnail_bbox") or bbox
            style = {**(spec.get("style") or {}), "geometry": spec.get("geometry", "polygon")}
            make_thumbnail_vector(norm, th, tbbox, style, thumb)
            assets["thumbnail"] = asset(th, MEDIA["png"], ["thumbnail"], _thumb_desc(thumb))
        extra_readme = [f"Features, {n}.", f"Cloud-native asset, {data_pq.name} (GeoParquet)."]
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
        assets["source"] = source_asset(local, src)
        # Band statistics live in STAC 1.1 core `bands`. The raster extension v2.0.0
        # schema conflicts with collection-level assets (spec issues #52 / #41), so
        # it is not declared here, projection carries the CRS.
        exts += [PROJ_EXT]
        if deriv.get("thumbnail", True):
            th = coll_dir / "thumbnail.png"
            tbbox = spec.get("thumbnail_bbox") or bbox
            make_thumbnail_raster(cog, th, tbbox, thumb)
            assets["thumbnail"] = asset(th, MEDIA["png"], ["thumbnail"], _thumb_desc(thumb))
        extra_readme = [f"Bands, {len(bands)}.", f"CRS, {code}.",
                        f"Cloud-native asset, {cog.name} (COG)."]

    elif kind == "tabular":
        data_pq = coll_dir / f"{stem}.parquet"
        data_name = data_pq.name
        to_table_parquet(local, data_pq)
        cols = table_columns(data_pq)
        n = feature_count(data_pq)
        bbox = None
        assets["data"] = asset(data_pq, MEDIA["parquet"], ["data"],
                               f"{spec['title']} (Parquet)",
                               {"table:columns": cols, "table:row_count": n})
        assets["source"] = source_asset(local, src)
        exts.append(TABLE_EXT)
        extra_readme = [f"Rows, {n}.", f"Columns, {len(cols)}.",
                        "Non-geospatial table, spatial requirements relaxed."]
    else:
        raise ValueError(f"unknown kind {kind}")

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
        extent["spatial"] = {"bbox": [[-180, -90, 180, 90]]}
    temporal = spec.get("temporal")
    if temporal:
        extent["temporal"] = {"interval": [temporal]}

    coll: dict[str, Any] = {
        "type": "Collection",
        "stac_version": STAC_VERSION,
        "stac_extensions": exts,
        "id": stem,
        "title": spec["title"],
        "description": spec["description"].strip(),
        "license": spec["license"],
        "keywords": spec.get("keywords", []),
        "providers": providers,
        "extent": extent,
        "assets": assets,
        "links": links,
    }
    if spec.get("attribution"):
        coll["attribution"] = spec["attribution"]
    if prov.get("updated"):
        coll["updated"] = prov["updated"]

    (coll_dir / "collection.json").write_text(json.dumps(coll, indent=2) + "\n")

    # sidecars, with format-specific open-it-in-code guidance
    open_lines, open_agents = open_snippet(kind, data_name)
    attribution = spec.get("attribution")
    readme_extra = [
        f"License, {spec['license']}." + (f" Attribution, {attribution}." if attribution else ""),
        f"Providers, {_providers_sentence(providers)}.",
        f"Original source, {src['url']} .",
    ] + extra_readme
    if not src.get("stable", True):
        readme_extra.append("Note, the upstream source is a live endpoint, so the source "
                            "checksum reflects the copy fetched at build time.")
    readme_extra += [""] + open_lines
    agents = [
        f"This collection holds {spec['title']}.",
        open_agents,
        ("For rendering use the visual PMTiles asset or the thumbnail."
         if assets.get("visual") else "For a quick preview use the thumbnail asset."),
        f"License is {spec['license']}."
        + (f" Attribute as {attribution}." if attribution else ""),
        f"The original upstream source is {src['url']} , tagged on the source-role asset.",
    ]
    write_sidecars(coll_dir, spec["title"], spec["description"].strip(), readme_extra, agents)

    return {"id": cid, "seg": seg, "title": spec["title"], "updated": prov.get("updated")}


# --------------------------------------------------------------- catalog build
def _group_meta(manifest: dict, seg: str) -> tuple[str, str]:
    entry = (manifest.get("catalogs", {}) or {}).get(seg)
    if entry:
        return entry["title"], entry["description"].strip()
    return seg.title(), f"{seg} Collections."


def build_catalog(manifest: dict, out: Path, cache: Path, only: str | None) -> None:
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

    # intermediate (nested) catalogs, titles come from the manifest
    for gseg, colls in groups.items():
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
        (gdir / "catalog.json").write_text(json.dumps(cat, indent=2) + "\n")
        write_sidecars(gdir, gtitle, gdesc,
                       [f"Collections, {len(colls)}."],
                       [f"This catalog groups {len(colls)} Collections under {gtitle}.",
                        "Follow the child links to each Collection."])

    # root catalog (only rebuild fully when not filtering to one collection)
    if not only:
        root_children = [
            link("child", f"./{g}/catalog.json", "application/json", _group_meta(manifest, g)[0])
            for g in groups
        ]
        root = {
            "type": "Catalog", "stac_version": STAC_VERSION, "stac_extensions": [SCHEMA_URI],
            "id": manifest["id"], "title": manifest["title"],
            "description": manifest["description"].strip(),
            "links": ([link("root", "./catalog.json", "application/json")]
                      + root_children + [dict(SIDE_LINKS[0]), dict(SIDE_LINKS[1])]),
        }
        if catalog_updated:
            root["updated"] = catalog_updated
        (out / "catalog.json").write_text(json.dumps(root, indent=2) + "\n")
        write_sidecars(out, manifest["title"], manifest["description"].strip(),
                       [f"Collections, {len(built)}.",
                        f"Nested Catalogs, {len(groups)}."],
                       [f"This is {manifest['title']}.",
                        "Follow the child links to each nested Catalog and Collection.",
                        "Every Collection carries a cloud-native data asset and cites its "
                        "original upstream source with a real checksum."])
