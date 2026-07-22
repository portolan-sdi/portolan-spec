# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.3",
#   "duckdb>=1.5.4",
#   "jsonschema>=4.26.0",
#   "pyarrow>=24",
#   "geoparquet-io @ git+https://github.com/yharby/geoparquet-io.git@f27e53108910f19bd74a9ff4be5c7d97b104753c",
# ]
# ///
"""
Portolan reference catalog generator.

Reads every YAML manifest in a directory and builds each one into its own
complete, v0.1-conformant Portolan STAC catalog. One manifest file describes one
whole catalog and holds everything catalog-specific, so this script carries no
per-catalog values. For each collection it downloads the true original source
once, converts it to a cloud-native canonical asset (GeoParquet for vector and
tabular, COG for raster), builds derivatives (PMTiles, thumbnail, MapLibre
styles), computes real file:size and sha2-256 multihash file:checksum for every
asset, and also cites the original file as a source-role asset. It validates the
output against the committed Portolan schema.

Prerequisites (FOSS, on PATH): GDAL 3.x (ogr2ogr, ogrinfo, gdal_translate,
gdalinfo, gdal_rasterize, gdal_create, gdalwarp) with the Parquet and COG
drivers, tippecanoe, and uv.

Run:
    uv run examples/build.py
    uv run examples/build.py --catalog reference
    uv run examples/build.py --only boundaries/us-counties
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any

import duckdb
import yaml

SCHEMA_URI = "https://schemas.portolan-sdi.org/portolan/v0.1.0/schema.json"
FILE_EXT = "https://stac-extensions.github.io/file/v2.1.0/schema.json"
WEBMAP_EXT = "https://stac-extensions.github.io/web-map-links/v1.3.0/schema.json"
RASTER_EXT = "https://stac-extensions.github.io/raster/v2.0.0/schema.json"
TABLE_EXT = "https://stac-extensions.github.io/table/v1.2.0/schema.json"
PROJ_EXT = "https://stac-extensions.github.io/projection/v2.0.0/schema.json"
ATTRIBUTION_EXT = "https://stac-extensions.github.io/attribution/v0.1.0/schema.json"
STAC_VERSION = "1.1.0"

MEDIA = {
    "geoparquet": "application/vnd.apache.parquet",
    "parquet": "application/vnd.apache.parquet",
    "cog": "image/tiff; application=geotiff; profile=cloud-optimized",
    "pmtiles": "application/vnd.pmtiles",
    "style": "application/vnd.mapbox.style+json",
    "png": "image/png",
}


# --------------------------------------------------------------------------- io
def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess:
    kw.setdefault("check", True)
    kw.setdefault("text", True)
    kw.setdefault("capture_output", True)
    p = subprocess.run(cmd, **kw)
    return p


def filesize(p: Path) -> int:
    return p.stat().st_size


def multihash(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    # sha2-256 multihash: 0x12 function code, 0x20 (32) digest length, then digest
    return (bytes([0x12, 0x20]) + h.digest()).hex()


def fetch(url: str, cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(url.encode()).hexdigest()[:16]
    tail = url.split("/")[-1].split("?")[0]
    suffix = "".join(c for c in tail if c.isalnum() or c in "._-")[-48:] or "download"
    dest = cache / f"{key}-{suffix}"
    if dest.exists() and dest.stat().st_size > 0:
        return dest
    print(f"  fetch {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "portolan-reference/0.1"})
    tmp = dest.with_suffix(dest.suffix + ".part")
    with urllib.request.urlopen(req, timeout=180) as r, tmp.open("wb") as f:
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
    tmp.rename(dest)
    return dest


def write_web_geoparquet(norm: Path, out_parquet: Path) -> None:
    """Write the canonical vector asset as a web-optimized GeoParquet 2.0 file.

    Delegates to geoparquet-io's web profile, the ecosystem's canonical writer
    and the only one that emits both native 2.0 GeospatialStatistics and a
    Parquet page index. The profile gives us a native geometry type, per row
    group statistics, a retained covering bbox column for page-level pruning,
    the page index, Hilbert spatial ordering, byte-targeted fetch-sized row
    groups, and ZSTD compression. `norm` must already be EPSG:4326."""
    from geoparquet_io import convert_geoparquet

    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    out_parquet.unlink(missing_ok=True)
    convert_geoparquet(str(norm), str(out_parquet),
                       optimize_for="web", compression_level=15)


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


# ------------------------------------------------------------------ conversions
def _is_zip(local: Path, spec_source: dict) -> bool:
    if spec_source.get("media_type") == "application/zip" or local.name.endswith(".zip"):
        return True
    with local.open("rb") as f:
        return f.read(2) == b"PK"


def _prepare_ogr_source(local: Path, spec_source: dict, extract_dir: Path) -> tuple[str, str | None]:
    """Return (gdal_path, layer_positional). Zip sources are extracted so the
    .shp (with its .prj/.cpg siblings) is read directly, independent of the
    cached filename's extension (GDAL /vsizip keys off a .zip suffix)."""
    layer = spec_source.get("layer")
    if _is_zip(local, spec_source):
        import zipfile
        if extract_dir.exists():
            import shutil
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)
        with zipfile.ZipFile(local) as z:
            z.extractall(extract_dir)
        shps = sorted(extract_dir.rglob("*.shp"))
        assert shps, f"no .shp found inside {local}"
        if layer:
            match = [s for s in shps if s.stem == layer]
            shp = match[0] if match else shps[0]
        else:
            shp = shps[0]
        return str(shp), None
    # gpkg / geojson / other single-file OGR source
    return str(local), layer


def to_geoparquet(local: Path, spec_source: dict, out_parquet: Path) -> tuple[list[float], int, Path]:
    """Normalize the source to EPSG:4326 with ogr2ogr into a GeoPackage, compute
    the bbox and feature count from it, then write the canonical asset as a
    web-optimized GeoParquet 2.0 file (see write_web_geoparquet).

    Returns (bbox, count, norm). The caller keeps `norm`, the EPSG:4326
    GeoPackage, to build derivatives (PMTiles, thumbnail, style sampling) that
    read it rather than the native 2.0 output, then deletes it."""
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    extract_dir = out_parquet.with_suffix(".src")
    src, layer = _prepare_ogr_source(local, spec_source, extract_dir)
    norm = out_parquet.with_suffix(".norm.gpkg")
    norm.unlink(missing_ok=True)
    cmd = ["ogr2ogr", "-t_srs", "EPSG:4326", "-f", "GPKG", "-nln", "layer", str(norm), src]
    if layer:
        cmd.append(layer)
    run(cmd)
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    minx, miny, maxx, maxy, n = con.execute(f"""
        SELECT ST_XMin(e), ST_YMin(e), ST_XMax(e), ST_YMax(e), c
        FROM (SELECT ST_Extent(ST_Union_Agg(geom)) e, count(*) c FROM ST_Read('{norm}'))
    """).fetchone()
    con.close()
    write_web_geoparquet(norm, out_parquet)
    if extract_dir.exists():
        import shutil
        shutil.rmtree(extract_dir)
    return [round(minx, 6), round(miny, 6), round(maxx, 6), round(maxy, 6)], int(n), norm


def feature_count(parquet: Path) -> int:
    con = duckdb.connect()
    n = con.execute(f"SELECT count(*) FROM read_parquet('{parquet}')").fetchone()[0]
    con.close()
    return int(n)


def to_cog(src_tif: Path, out_tif: Path) -> None:
    out_tif.parent.mkdir(parents=True, exist_ok=True)
    run(["gdal_translate", "-of", "COG", "-co", "COMPRESS=DEFLATE",
         "-co", "STATISTICS=YES", str(src_tif), str(out_tif)])


def _gdalinfo(tif: Path) -> dict:
    return json.loads(run(["gdalinfo", "-json", "-stats", str(tif)]).stdout)


# GDAL band type -> STAC core `bands` data_type enum value
GDAL_DTYPE = {
    "Byte": "uint8", "Int8": "int8", "Int16": "int16", "UInt16": "uint16",
    "Int32": "int32", "UInt32": "uint32", "Int64": "int64", "UInt64": "uint64",
    "Float32": "float32", "Float64": "float64",
    "CInt16": "cint16", "CInt32": "cint32", "CFloat32": "cfloat32", "CFloat64": "cfloat64",
}


def bands_from_cog(tif: Path) -> list[dict]:
    info = _gdalinfo(tif)
    out = []
    for b in info["bands"]:
        meta = b.get("metadata", {}).get("", {})
        stats = {}
        for key, name in [("STATISTICS_MINIMUM", "minimum"), ("STATISTICS_MAXIMUM", "maximum"),
                          ("STATISTICS_MEAN", "mean"), ("STATISTICS_STDDEV", "stddev")]:
            if key in meta:
                stats[name] = round(float(meta[key]), 4)
        band: dict[str, Any] = {"data_type": GDAL_DTYPE.get(b.get("type", ""), "other")}
        if stats:
            band["statistics"] = stats
        out.append(band)
    return out


def proj_code(tif: Path) -> str:
    wkt = _gdalinfo(tif).get("coordinateSystem", {}).get("wkt", "")
    ids = re.findall(r'ID\["EPSG",(\d+)\]', wkt)
    return f"EPSG:{ids[-1]}" if ids else ""


def bbox_wgs84_raster(tif: Path) -> list[float]:
    ext = _gdalinfo(tif)["wgs84Extent"]["coordinates"][0]
    xs = [p[0] for p in ext]
    ys = [p[1] for p in ext]
    return [round(min(xs), 6), round(min(ys), 6), round(max(xs), 6), round(max(ys), 6)]


def to_table_parquet(csv: Path, out_parquet: Path) -> None:
    out_parquet.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"""
        COPY (SELECT * FROM read_csv_auto('{csv}', sample_size=-1, all_varchar=false))
        TO '{out_parquet}' (FORMAT PARQUET, COMPRESSION zstd);
    """)
    con.close()


def table_columns(parquet: Path) -> list[dict]:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet('{parquet}')").fetchall()
    con.close()
    return [{"name": r[0], "type": r[1].lower()} for r in rows]


# ------------------------------------------------------------------ derivatives
def make_pmtiles(vector_src: Path, out_pmtiles: Path, layer_name: str) -> None:
    seq = out_pmtiles.with_suffix(".geojsonl")
    seq.unlink(missing_ok=True)
    run(["ogr2ogr", "-f", "GeoJSONSeq", str(seq), str(vector_src)])
    run(["tippecanoe", "-o", str(out_pmtiles), "--force", "-zg",
         "--drop-densest-as-needed", "--extend-zooms-if-still-dropping",
         "-l", layer_name, str(seq)])
    seq.unlink(missing_ok=True)


# Thumbnails render in Web Mercator (EPSG:3857) at the data's true aspect ratio,
# over a CARTO light XYZ tile basemap, so previews read as real maps rather than
# stretched squares. GDAL pulls only the tiles the framed extent needs, at the
# zoom that matches the output resolution, and caches them under .cache. Features
# are painted from the same `style` block that drives the MapLibre styles, so the
# preview mirrors the real cartography. All feature rasterization goes through
# GeoPackage intermediates (GeoJSON is always WGS84 and would silently drop the
# projected SRS).
_MERC_R = 6378137.0

# Categorical palette shared by the thumbnails and the MapLibre styles, so a
# collection reads the same across both. Tableau 10 minus grey.
PALETTE = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#b07aa1",
           "#76b7b2", "#edc948", "#ff9da7"]


def _sql_lit(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _to_merc(lon: float, lat: float) -> tuple[float, float]:
    lat = max(min(lat, 85.06), -85.06)
    return _MERC_R * math.radians(lon), _MERC_R * math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _thumb_grid(bbox4326: list[float], size: int, pad: float) -> tuple[list[float], list[float], int, int]:
    """Pad the WGS84 bbox, clamp to the Mercator-valid range, and return the
    padded bbox, its Mercator extent, and a pixel size at the true aspect ratio."""
    minx, miny, maxx, maxy = bbox4326
    dx = (maxx - minx) or 1e-4
    dy = (maxy - miny) or 1e-4
    minx -= dx * pad; maxx += dx * pad
    miny -= dy * pad; maxy += dy * pad
    minx = max(minx, -180.0); maxx = min(maxx, 180.0)
    miny = max(miny, -85.06); maxy = min(maxy, 85.06)
    x0, y0 = _to_merc(minx, miny)
    x1, y1 = _to_merc(maxx, maxy)
    mdx = (x1 - x0) or 1.0
    mdy = (y1 - y0) or 1.0
    if mdx >= mdy:
        w, h = size, max(1, round(size * mdy / mdx))
    else:
        w, h = max(1, round(size * mdx / mdy)), size
    return [minx, miny, maxx, maxy], [x0, y0, x1, y1], w, h


def _ogr_count(src: Path) -> int:
    out = json.loads(run(["ogrinfo", "-so", "-json", str(src)]).stdout)
    return sum(int(l.get("featureCount", 0) or 0) for l in out.get("layers", []))


def _tile_basemap_xml(url: str, cache: Path) -> Path:
    """Write a GDAL WMS TMS descriptor for an XYZ raster basemap (CARTO light by
    default). gdalwarp then reads it like any raster, fetching only the tiles the
    thumbnail extent needs at the zoom that matches the output resolution, and
    caching them on disk so repeat builds do not refetch."""
    tiles = cache / "tiles"
    tiles.mkdir(parents=True, exist_ok=True)
    xml = cache / "basemap.xml"
    xml.write_text(
        "<GDAL_WMS>\n"
        '  <Service name="TMS">\n'
        f"    <ServerUrl>{url}</ServerUrl>\n"
        "  </Service>\n"
        "  <DataWindow>\n"
        "    <UpperLeftX>-20037508.342789244</UpperLeftX>\n"
        "    <UpperLeftY>20037508.342789244</UpperLeftY>\n"
        "    <LowerRightX>20037508.342789244</LowerRightX>\n"
        "    <LowerRightY>-20037508.342789244</LowerRightY>\n"
        "    <TileLevel>18</TileLevel>\n"
        "    <TileCountX>1</TileCountX>\n"
        "    <TileCountY>1</TileCountY>\n"
        "    <YOrigin>top</YOrigin>\n"
        "  </DataWindow>\n"
        "  <Projection>EPSG:3857</Projection>\n"
        "  <BlockSizeX>256</BlockSizeX>\n"
        "  <BlockSizeY>256</BlockSizeY>\n"
        "  <BandsCount>3</BandsCount>\n"
        "  <UserAgent>portolan-reference/0.1</UserAgent>\n"
        f"  <Cache><Path>{tiles}</Path></Cache>\n"
        "</GDAL_WMS>\n"
    )
    return xml


def _make_canvas(canvas: Path, thumb: dict, merc: list[float], w: int, h: int) -> None:
    """Build the Mercator canvas, the CARTO tile basemap warped to the framed
    extent, or a flat ocean fill when no basemap is configured."""
    x0, y0, x1, y1 = merc
    canvas.unlink(missing_ok=True)
    if thumb.get("basemap"):
        run(["gdalwarp", "-q", "-of", "GTiff", "-t_srs", "EPSG:3857",
             "-te", str(x0), str(y0), str(x1), str(y1), "-ts", str(w), str(h),
             "-r", "bilinear", str(thumb["basemap"]), str(canvas)])
    else:
        ocean = thumb["ocean"]
        run(["gdal_create", "-of", "GTiff", "-bands", "3", "-outsize", str(w), str(h),
             "-a_srs", "EPSG:3857", "-a_ullr", str(x0), str(y1), str(x1), str(y0),
             "-burn", str(ocean[0]), "-burn", str(ocean[1]), "-burn", str(ocean[2]), str(canvas)])


def _clip_to_canvas(src: Path, bbox4326: list[float], gpkg: Path) -> int:
    """Reproject and clip a vector source into a Mercator GeoPackage. Clipping to
    the padded bbox also keeps sub-85-degree geometry finite. Returns feature count."""
    minx, miny, maxx, maxy = bbox4326
    gpkg.unlink(missing_ok=True)
    run(["ogr2ogr", "-t_srs", "EPSG:3857", "-clipsrc", str(minx), str(miny), str(maxx), str(maxy),
         "-nln", "layer", "-f", "GPKG", str(gpkg), str(src)])
    return _ogr_count(gpkg)


def _rasterize(canvas: Path, gpkg: Path, rgb: tuple[int, int, int], where: str | None = None) -> None:
    cmd = ["gdal_rasterize", "-l", "layer", "-b", "1", "-b", "2", "-b", "3",
           "-burn", str(rgb[0]), "-burn", str(rgb[1]), "-burn", str(rgb[2])]
    if where:
        cmd += ["-where", where]
    cmd += [str(gpkg), str(canvas)]
    run(cmd)


def _buffer_points(gpkg: Path, radius_m: float, keep_field: str | None) -> Path:
    """Grow point features into small circles so they read as visible dots.
    gdal_rasterize paints a raw point as a single pixel, which vanishes at world
    scale. The radius is passed in metres, sized from the pixel resolution, so
    dots stay the same on-screen size at any extent. Any category field is kept
    so per-category colouring still works."""
    out = gpkg.with_suffix(".buf.gpkg")
    out.unlink(missing_ok=True)
    cols = f', "{keep_field}"' if keep_field else ""
    run(["ogr2ogr", "-f", "GPKG", "-dialect", "SQLITE", "-nln", "layer",
         "-sql", f"SELECT ST_Buffer(geom, {radius_m}) AS geom{cols} FROM layer", str(out), str(gpkg)])
    return out


def _burn_outline(canvas: Path, gpkg: Path, rgb: tuple[int, int, int]) -> None:
    """Overlay polygon boundaries as thin lines so neighbouring features stay
    distinct even when they share a categorical colour (counties within a state)."""
    lines = gpkg.with_suffix(".lines.gpkg")
    lines.unlink(missing_ok=True)
    run(["ogr2ogr", "-f", "GPKG", "-dialect", "SQLITE", "-nln", "layer",
         "-sql", "SELECT ST_Boundary(geom) AS geom FROM layer", str(lines), str(gpkg)])
    if _ogr_count(lines):
        _rasterize(canvas, lines, rgb)
    lines.unlink(missing_ok=True)


def make_thumbnail_vector(vector_src: Path, out_png: Path, bbox4326: list[float],
                          style: dict, thumb: dict) -> None:
    """Paint the features over the basemap using the collection `style` block. A
    categorical field colours by category from the shared palette, otherwise the
    default colour fills flat. Polygons get a thin outline for granularity."""
    b, merc, w, h = _thumb_grid(bbox4326, thumb["size"], thumb["pad_vector"])
    canvas = out_png.with_suffix(".canvas.tif")
    _make_canvas(canvas, thumb, merc, w, h)
    gpkg = canvas.with_suffix(".feat.gpkg")
    if _clip_to_canvas(vector_src, b, gpkg):
        field = style.get("category_field")
        if style.get("geometry", "polygon") == "point":
            radius_m = (merc[2] - merc[0]) / w * 2.5
            buf = _buffer_points(gpkg, radius_m, field)
            gpkg.unlink(missing_ok=True)
            gpkg = buf
        if field:
            for val, hexc in _category_colors(vector_src, field, style.get("palette")):
                _rasterize(canvas, gpkg, _hex_rgb(hexc), where=f'"{field}" = {_sql_lit(val)}')
        else:
            _rasterize(canvas, gpkg, _hex_rgb(style.get("color", "#3388ff")))
        if style.get("geometry", "polygon") == "polygon":
            _burn_outline(canvas, gpkg, _hex_rgb(style.get("outline", "#ffffff")))
    gpkg.unlink(missing_ok=True)
    run(["gdal_translate", "-of", "PNG", str(canvas), str(out_png)])
    canvas.unlink(missing_ok=True)
    Path(str(out_png) + ".aux.xml").unlink(missing_ok=True)


def make_thumbnail_raster(tif: Path, out_png: Path, bbox4326: list[float], thumb: dict) -> None:
    b, merc, w, h = _thumb_grid(bbox4326, thumb["size"], thumb["pad_raster"])
    canvas = out_png.with_suffix(".canvas.tif")
    _make_canvas(canvas, thumb, merc, w, h)
    # warp the raster onto the basemap canvas, treating 0 as transparent nodata
    run(["gdalwarp", "-q", "-r", "bilinear", "-srcnodata", "0", "-dstnodata", "0", str(tif), str(canvas)])
    run(["gdal_translate", "-of", "PNG", str(canvas), str(out_png)])
    canvas.unlink(missing_ok=True)
    Path(str(out_png) + ".aux.xml").unlink(missing_ok=True)


def build_thumb_ctx(manifest: dict, cache: Path) -> dict:
    """Read the manifest thumbnails block and prepare the shared tile basemap
    descriptor once. Everything thumbnail-specific lives in the manifest, not here.
    The basemap is an XYZ tile template (`{z}/{x}/{y}`), CARTO light by default."""
    t = manifest.get("thumbnails", {}) or {}
    basemap = None
    attribution = None
    bm = t.get("basemap")
    if bm:
        url = bm["url"] if isinstance(bm, dict) else bm
        attribution = bm.get("attribution") if isinstance(bm, dict) else None
        basemap = _tile_basemap_xml(url, cache)
    return {
        "size": int(t.get("size", 768)),
        "pad_vector": float(t.get("pad_vector", 0.06)),
        "pad_raster": float(t.get("pad_raster", 0.4)),
        "ocean": _hex_rgb(t.get("ocean_color", "#eef3f8")),
        "basemap": basemap,
        "attribution": attribution,
    }


def _thumb_desc(thumb: dict) -> str:
    if thumb.get("attribution"):
        return f"Preview thumbnail over a light basemap. {thumb['attribution']}."
    return "Preview thumbnail"


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
    source = {layer: {"type": "vector", "url": f"pmtiles://./{pmtiles_name}"}}

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
        layers = [{"id": layer, "type": gl_type, "source": layer,
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
                    "id": f"{layer}-labels", "type": "symbol", "source": layer,
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
                     thumb: dict) -> dict:
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

    print(f"[{cid}] fetch + convert ({kind})", file=sys.stderr)
    local = fetch(src["url"], cache)

    exts = [SCHEMA_URI, FILE_EXT]
    assets: dict[str, dict] = {}
    links: list[dict] = []
    layer_name = stem
    deriv = spec.get("derivatives", {}) or {}
    data_name = ""

    if kind in ("vector",):
        data_pq = coll_dir / f"{stem}.parquet"
        data_name = data_pq.name
        bbox, n, norm = to_geoparquet(local, src, data_pq)
        cols = table_columns(data_pq)
        geom_col = next((c["name"] for c in cols if c["type"] == "geometry"), "geom")
        assets["data"] = asset(data_pq, MEDIA["geoparquet"], ["data"],
                               f"{spec['title']} (GeoParquet)",
                               {"table:columns": cols, "table:primary_geometry": geom_col,
                                "table:row_count": n, "proj:code": "EPSG:4326"})
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
        to_cog(local, cog)
        bands = bands_from_cog(cog)
        code = proj_code(cog)
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
    built = [build_collection(s, manifest["host"], out, cache, thumb) for s in specs]

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


def collection_findings(obj: dict) -> list[str]:
    """Return Portolan provenance findings the JSON schema delegates to tooling.

    Checks the two rules the schema leaves to the validator, that a collection
    has exactly one host provider and that it is the last element, and that a
    collection whose license is `other` carries a rel=license link."""
    out: list[str] = []
    provs = obj.get("providers", []) or []
    host_idx = [i for i, p in enumerate(provs) if "host" in (p.get("roles") or [])]
    if len(host_idx) != 1:
        out.append(f"providers must have exactly one host, found {len(host_idx)}")
    elif host_idx[0] != len(provs) - 1:
        out.append("host provider must be listed last")
    if obj.get("license") == "other":
        if not any(lk.get("rel") == "license" for lk in obj.get("links", []) or []):
            out.append("license is 'other' but no rel=license link is present")
    return out


# ------------------------------------------------------------------- validation
def validate(out: Path, schema_path: Path) -> None:
    import jsonschema  # noqa

    schema = json.loads(schema_path.read_text())
    validator = jsonschema.Draft7Validator(schema)
    errors = 0
    for jf in sorted(out.rglob("*.json")):
        obj = json.loads(jf.read_text())
        if obj.get("type") not in ("Catalog", "Collection", "Feature"):
            continue
        for e in validator.iter_errors(obj):
            errors += 1
            print(f"  SCHEMA {jf.relative_to(out)}: {e.message}", file=sys.stderr)
        # extra Portolan checks the schema delegates to tooling
        for a in obj.get("assets", {}).values():
            ck = a.get("file:checksum", "")
            if not re.fullmatch(r"1220[0-9a-f]{64}", ck):
                errors += 1
                print(f"  CHECKSUM {jf.relative_to(out)}: not a sha2-256 multihash: {ck}", file=sys.stderr)
        for lk in obj.get("links", []):
            if lk.get("rel") == "self":
                errors += 1
                print(f"  SELF-LINK {jf.relative_to(out)}", file=sys.stderr)
        if obj.get("type") == "Collection":
            for msg in collection_findings(obj):
                errors += 1
                print(f"  PROVENANCE {jf.relative_to(out)}: {msg}", file=sys.stderr)
    if errors:
        raise SystemExit(f"validation failed with {errors} error(s)")
    print(f"validation passed for {out}", file=sys.stderr)


# ------------------------------------------------------------------------- main
def _repo_root() -> Path:
    # examples/build.py -> repo root is the parent of examples/
    return Path(__file__).resolve().parent.parent


def main() -> int:
    root = _repo_root()
    ap = argparse.ArgumentParser(description="Generate Portolan catalogs from manifests")
    ap.add_argument("--manifests", default=root / "examples/manifests", type=Path,
                    help="directory of *.yaml catalog manifests")
    ap.add_argument("--out", default=root / "examples/catalog", type=Path,
                    help="output root, each manifest builds into <out>/<stem>")
    ap.add_argument("--cache", default=root / "examples/.cache", type=Path)
    ap.add_argument("--catalog", default=None, help="build only the manifest with this file stem")
    ap.add_argument("--only", default=None, help="build only this collection id")
    ap.add_argument("--schema", default=root / "stac/json-schema/v0.1.0/schema.json", type=Path)
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args()

    files = sorted(p for p in args.manifests.glob("*.yaml"))
    files += sorted(p for p in args.manifests.glob("*.yml"))
    if args.catalog:
        files = [p for p in files if p.stem == args.catalog]
    if not files:
        raise SystemExit(f"no manifests found in {args.manifests}")

    for mf in files:
        print(f"=== manifest {mf.name} ===", file=sys.stderr)
        manifest = load_manifest(mf)
        cat_out = args.out / mf.stem
        build_catalog(manifest, cat_out, args.cache, args.only)
        if not args.no_validate and not args.only:
            validate(cat_out, args.schema)
    print("done", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
