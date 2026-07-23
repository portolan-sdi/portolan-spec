# examples/tools/, Portolan reference catalog generator

This directory holds the generator, a minimal open-source tool that turns YAML
manifests into complete, v0.1-conformant Portolan STAC catalogs. It is a small
set of plain sibling modules run through the `build.py` entrypoint. The manifests
it reads and the catalog it produces live one level up under `examples/`. Read
this before editing the generator.

## Layout

The generator is a set of modules under `examples/tools/`, each owning one
responsibility. Only `build.py` and the two test files are `uv run` entrypoints
and carry a PEP 723 header. The sibling modules are plain modules, and `build.py`
bootstraps `sys.path` with its own directory so they import as flat names.

| Module | Responsibility |
|--------|----------------|
| `build.py` | Entrypoint. PEP 723 header, argparse, `main`, resolves paths from the repo root |
| `config.py` | Static constants, extension URIs, media types, GDAL band-type map, palette |
| `common.py` | Shared helpers, subprocess runner, checksums, value formatting |
| `fetch.py` | Downloads sources into `.cache` and unpacks zipped shapefiles |
| `convert.py` | Format conversions, vector to GeoParquet, raster to COG, CSV to Parquet |
| `derivatives.py` | PMTiles tiles and data-driven MapLibre styles |
| `thumbnails.py` | Web Mercator preview rendering over the tile basemap |
| `stacio.py` | STAC assembly, manifest, providers, assets, links, sidecars, catalog builders |
| `validate.py` | JSON schema plus the Portolan conformance rules tooling owns |
| `tests/` | Standalone `uv run` checks, `check_compliance.py` and `check_web_output.py` |

Inputs and outputs live under `examples/`, not here.

| Path | What it is |
|------|------------|
| `../manifests/*.yaml` | Inputs. One file describes one whole catalog |
| `../catalog/<stem>/` | Output. One STAC tree per manifest, named after the file stem |
| `../.cache/` | Downloaded upstream sources, git-ignored, safe to delete |

## Running it

```bash
uv run examples/tools/build.py                                # build every manifest
uv run examples/tools/build.py --catalog reference            # one manifest by stem
uv run examples/tools/build.py --only boundaries/us-counties  # one Collection, skips validation
```

`uv` reads the PEP 723 header at the top of `build.py` and resolves the Python
deps (pyyaml, duckdb, jsonschema, pyarrow, and the pinned geoparquet-io) on the
fly. External tools must be on PATH, GDAL 3.x (`ogr2ogr`, `ogrinfo`,
`gdal_translate`, `gdalinfo`, `gdal_rasterize`, `gdal_create`, `gdalwarp`) with
the Parquet and COG drivers, and `tippecanoe`.

The two test suites run the same way.

```bash
uv run examples/tools/tests/check_compliance.py
uv run examples/tools/tests/check_web_output.py
```

## The core principle

Everything catalog-specific lives in the manifest, never in the generator. That
includes the catalog id and title, the nested-catalog titles, thumbnail colors,
and the basemap. If you find yourself adding a catalog-specific value to the
Python, put it in the manifest instead and read it back.

## Manifest schema

Top level of each file in `manifests/`.

- `id`, `title`, `description`. Root Catalog identity.
- `schema_uri`. Must equal the pinned v0.1.0 URI. `load_manifest` asserts this.
- `host`. `{name, url, email}`. Appended as the `host`-role provider on mirror Collections.
- `catalogs`. Map from the first id segment to `{title, description}` for each nested Catalog.
- `thumbnails`. `{size, ocean_color, pad_vector?, pad_raster?, basemap: {url, attribution?}}`. The basemap is an XYZ raster tile URL template with `{z}/{x}/{y}` placeholders, CARTO light by default.
- `collections`. The list below.

Each entry in `collections`.

- `id`. A path like `boundaries/us-counties`. The first segment is the nested Catalog, the last is the Collection id.
- `kind`. One of `vector`, `raster`, `tabular`. Selects the conversion path.
- `geometry`. `polygon`, `point`, or `line`. Vector only, drives style and thumbnail paint.
- `title`, `description`, `keywords`, `license`, `attribution?`.
- `license_url?`. Required only when `license` is `other`. The URL of the license text. The generator emits the mandatory `rel: license` link from it.
- `source`. `{url, media_type, title, layer?, stable}`. The true original upstream file. `stable: false` marks a live endpoint.
- `providers`. List of `{name, url, roles}`. Roles are `producer`, `licensor`, `processor`, `host`.
- `provenance`. `{via?, canonical?, updated?}`.
- `temporal`. `[start, end_or_null]`.
- `thumbnail_bbox?`. `[minx, miny, maxx, maxy]`. Frames the preview only, not the data. Use it for antimeridian-spanning data.
- `derivatives`. `{pmtiles, thumbnail}`. Booleans that toggle the PMTiles and thumbnail outputs.
- `style?`. Per-Collection paint, `{color, outline, opacity, palette?, category_field?, label_field?, graduated_field?, variants?}`. Drives both the MapLibre styles and the thumbnail paint. `category_field` colours by category from the shared palette, `graduated_field` interpolates a numeric ramp, `label_field` adds labels, and `variants` lists which style files to author.

## Provenance is derived, not declared

`resolve_providers` decides official versus mirror from the provider roles, there
is no explicit flag.

- If any provider carries the `host` role, the Collection is official. The Portolan host is not appended.
- Otherwise it is a mirror. The `host` block is appended with a `host` role, and `check_provenance` requires `provenance.via` and `provenance.updated`. It raises if either is missing.

Mirrors get a `via` link, and any Collection with `provenance.canonical` gets a
`canonical` link.

- `resolve_providers` guarantees exactly one host provider, moved to the last position, and raises if a manifest lists more than one. `validate` gates both this host-order rule and the `license: other` link rule, failing the build if either is violated.

## Pipeline per kind

Every path downloads the source once into `.cache`, produces a cloud-native
canonical `data` Asset, and also emits a `source`-role Asset that points at the
upstream URL with the real `file:size` and multihash `file:checksum` of the
fetched file.

- `vector`. `to_geoparquet` normalizes to EPSG:4326 with ogr2ogr into a GeoPackage, computes the bbox and count from it, then writes the canonical asset as a web-optimized GeoParquet 2.0 file with geoparquet-io's web profile (native geometry type, per row group GeospatialStatistics, a retained covering bbox column for page-level pruning, a Parquet page index, Hilbert ordering, and byte-targeted fetch-sized row groups). Derivatives read the normalized GeoPackage, not the 2.0 output. Optional PMTiles come from ogr2ogr GeoJSONSeq into tippecanoe, with a web-map-links `pmtiles` link. Optional MapLibre styles are authored by `author_styles` from the real field values and read the PMTiles. The GeoParquet `data` asset also carries `table:columns` from a DuckDB `DESCRIBE`, geometry column included, and `proj:code` `EPSG:4326`, declaring the table and projection extensions.
- `raster`. `to_cog` builds a COG with embedded statistics. Band statistics go in STAC 1.1 core `bands`, and `proj:code` carries the CRS through the projection extension.
- `tabular`. `to_table_parquet` reads the CSV with DuckDB and writes Parquet. Columns are described with the table extension. No geometry, the spatial extent is the whole world and spatial rules are relaxed.

A Collection whose manifest sets `attribution` declares the attribution extension and carries a top-level `attribution` field.

## Output structure

Per manifest, the tree is `catalog/<stem>/`.

- Root `catalog.json` at the top, one nested `catalog.json` per id segment, one `collection.json` per Collection.
- Links are relative for structure (`root`, `parent`, `child`) and absolute https for upstream. Child links are titled. There are no `self` links.
- Every node carries an `agents` link to its `AGENTS.md` and a `describedby` link to its `README.md`, both generated. The Collection README includes runnable open-it code chosen by kind, GeoPandas or DuckDB for GeoParquet, pandas or DuckDB for Parquet, rioxarray or rasterio for the COG.

## Thumbnails

Thumbnails render in Web Mercator (EPSG:3857) at the data's true aspect ratio
over a CARTO light XYZ tile basemap, so they read as real maps rather than
stretched squares. `_thumb_grid` pads the bbox, clamps latitude to the
Mercator-valid range, and sizes the canvas to the projected aspect.
`_tile_basemap_xml` writes a GDAL WMS descriptor so `gdalwarp` fetches only the
tiles the framed extent needs and caches them under `.cache`. `_make_canvas`
warps that basemap onto the canvas, or fills flat ocean when no basemap is set.
`_clip_to_canvas` reprojects and clips the vector source into a Mercator
GeoPackage, `_rasterize` burns features from the collection `style` block, and
`_burn_outline` overlays polygon boundaries. Rasters are warped on top with
`gdalwarp`.

## Gotchas, learned the hard way

- The final vector write goes through geoparquet-io, pinned to the PR #573 fork commit, the only path that emits a Parquet page index together with native GeoParquet 2.0 GeospatialStatistics. DuckDB and ogr2ogr cannot write the page index.
- GeoJSON is always WGS84 and silently drops any target SRS. The thumbnail path uses GeoPackage intermediates so the Mercator projection survives.
- `gdal_rasterize` writes only band 1 by default. Pass `-b 1 -b 2 -b 3` to fill an RGB canvas.
- Zip sources are extracted before reading, because GDAL `/vsizip` keys off a `.zip` suffix that the cached filename does not have.
- The raster extension v2.0.0 is not declared, its schema conflicts with Collection-level assets (spec issues #52 and #41). Statistics still ship in core `bands`.
- The Boston, San Francisco, and Eurostat sources are live endpoints, so their `source` checksums are point-in-time and each README says so.

## Validation

`validate` runs after each catalog unless `--only` or `--no-validate` is set. It
checks every Catalog, Collection, and Feature against the committed schema at
`../../stac/json-schema/v0.1.0/schema.json`, verifies each `file:checksum` is a
sha2-256 multihash, and fails on any `self` link. The tree also passes the
ecosystem `stac-node-validator` when pointed at the same schema with
`--schemaMap`.

## Conventions

- Use the official STAC names everywhere, Catalog, nested Catalog, Collection, Item, Asset. Never write "dataset".
- Generated prose in `README.md` and `AGENTS.md` avoids em dashes, colons, and semicolons, matching the project writing style. Keep new generated copy the same.
- Keep the generator dependency-light, small modules each with one responsibility. Prefer the manifest and standard FOSS tools over new Python dependencies. When code moves between modules, keep imports explicit, no wildcard imports.
