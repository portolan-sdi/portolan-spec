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
| `thumbnails.py` | Web Mercator preview rendering over the tile basemap fetched by `tiles.py` |
| `tiles.py` | XYZ basemap tile fetch and mosaic for thumbnails |
| `stacio.py` | STAC assembly, manifest, providers, assets, links, sidecars, catalog builders |
| `validate.py` | Thin adapter over reis, the canonical validator. Runs its metadata, structural, schema, and data passes over the built catalog |
| `tests/` | Standalone `uv run` checks, `check_compliance.py`, `check_web_output.py`, `check_validate.py`, `check_tiles.py`, `check_thumb_geoms.py`, `check_thumbnails.py`, `check_cog.py`, `check_fetch.py`, and `check_styles.py` |

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
deps (pyyaml, duckdb, jsonschema, pyarrow, rasterio, rio-cogeo, and the pinned
geoparquet-io) on the fly. The whole generator, data path and thumbnails
alike, runs on DuckDB spatial, rasterio, and rio-cogeo, none of it shells out
to the GDAL CLI, so the only prerequisites on PATH are `tippecanoe` and `uv`.

The test scripts run the same way.

```bash
uv run examples/tools/tests/check_compliance.py
uv run examples/tools/tests/check_web_output.py
uv run examples/tools/tests/check_validate.py
uv run examples/tools/tests/check_tiles.py
uv run examples/tools/tests/check_thumb_geoms.py
uv run examples/tools/tests/check_thumbnails.py
uv run examples/tools/tests/check_cog.py
uv run examples/tools/tests/check_fetch.py
uv run examples/tools/tests/check_styles.py
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
- `output_crs?`. Optional output CRS for the canonical assets, for example `EPSG:4326`. Source-preserving by default, set at the top level for the whole catalog, or per collection to override just that one.
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
- `style?`. Per-Collection paint, `{color, outline, opacity, palette?, category_field?, label_field?, graduated_field?, variants?}`. Drives both the MapLibre styles and the thumbnail paint. `category_field` colours by category from the shared palette, `graduated_field` interpolates a numeric ramp, `label_field` adds labels, and `variants` lists which style files to author. The FIRST variant is the default style and is what the thumbnail renders.
- `columns?`. `{column_name: description}`. Merged into `table:columns` by `describe_columns`. A Parquet footer carries names and types but no semantics, so the prose has to come from the manifest. Required in spirit for `tabular`, where the column schema is the only semantic handle a consumer gets.
- `bbox?`. Tabular only. The area of interest the table pertains to, which core.md asks for in place of a geometric footprint. Absent, the fallback is the whole world, correct only for a genuinely global table.
- `join?`. Tabular only. `{column, target, target_column, target_file, note?}`. Emits the README join section and a runnable DuckDB example, which formats.md requires whenever geometry and attributes live in separate files. `target_file` is relative to the Collection directory.

## Provenance is derived, not declared

`resolve_providers` decides official versus mirror from the provider roles, there
is no explicit flag.

- If any provider carries the `host` role, the Collection is official. The Portolan host is not appended.
- Otherwise it is a mirror. The `host` block is appended with a `host` role, and `check_provenance` requires `provenance.via` and `provenance.updated`. It raises if either is missing.

Mirrors get a `via` link, and any Collection with `provenance.canonical` gets a
`canonical` link.

Every Collection in the reference manifest is a mirror, and no `canonical` link
is emitted anywhere. Both follow from the spec rather than from convenience.
core.md ties `host` to whoever operates *this copy* and says an organization
hosting data it did not produce is a mirror "even when it is the primary
distributor". Portolan SDI serves every asset in the tree and produced none of
the data, so naming an upstream producer as host would be false. The official
branch can only be exercised by a catalog whose publisher originates the data.
`canonical` is owed only when the upstream publishes its own STAC, and none of
these eight do, so the eight PTL-PRO-002 infos are the correct outcome, not
something to silence with a link to a landing page or an ISO record.

- `resolve_providers` guarantees exactly one host provider, moved to the last position, and raises if a manifest lists more than one. `validate` gates both this host-order rule and the `license: other` link rule, failing the build if either is violated.

## Pipeline per kind

Every path downloads the source into `.cache` and produces a cloud-native
canonical `data` Asset. When the manifest marks the source `stable: true`, it
also emits a `source`-role Asset that points at the upstream URL with the real
`file:size` and multihash `file:checksum` of the fetched file. A `stable: false`
source, meaning a live endpoint, is referenced by URL in the sidecars only,
because pinned checksums on bytes the catalog does not control are guaranteed to
rot. `add_source_asset` is the single gate.

- `vector`. `to_geoparquet` converts with DuckDB spatial, preserving the source CRS or the manifest `output_crs`, and also builds a WGS84 GeoPackage for the bbox, the PMTiles feed, the thumbnail, and style sampling. It then writes the canonical asset as a web-optimized GeoParquet 2.0 file with geoparquet-io's web profile (native geometry type, per row group GeospatialStatistics, a retained covering bbox column for page-level pruning, a Parquet page index, Hilbert ordering, and byte-targeted fetch-sized row groups). Derivatives read the WGS84 GeoPackage, not the 2.0 output. Optional PMTiles come from a DuckDB GeoJSONSeq export into tippecanoe, with a web-map-links `pmtiles` link. Optional MapLibre styles are authored by `author_styles` from the real field values and read the PMTiles. The GeoParquet `data` asset also carries `table:columns` from a DuckDB `DESCRIBE`, geometry column included, and `proj:code` derived from the real output CRS, declaring the table and projection extensions.
- `raster`. `to_cog` builds the COG with rasterio, preserving the source CRS or warping to the manifest `output_crs`. Band statistics come from rasterio and numpy and go in STAC 1.1 core `bands`, minimum, maximum, mean, stddev, and valid percent, and `proj:code` carries the real output CRS through the projection extension. The same values are embedded as GDAL `STATISTICS_*` band tags, which is where reis reads them. Overview depth is left to rio-cogeo rather than pinned, see the gotcha below.
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
`tiles.fetch_basemap` fetches and mosaics the covering XYZ tiles into a numpy
RGB canvas, caching each tile under `.cache`, or the canvas fills flat ocean
when no basemap is set. `_mercator_geoms` reprojects and clips the WGS84
vector source into EPSG:3857 with DuckDB spatial, returning the feature and
outline geometries. `_burn` rasterizes those features and polygon outlines
onto the canvas with `rasterio.features`. Rasters are warped on top with
`rasterio.warp.reproject`. Pillow writes the final PNG.

## Gotchas, learned the hard way

- The final vector write goes through geoparquet-io, pinned to the PR #573 fork commit, the only path that emits a Parquet page index together with native GeoParquet 2.0 GeospatialStatistics. DuckDB and ogr2ogr cannot write the page index.
- GeoJSON is always WGS84 and silently drops any target SRS. The thumbnail path reads the WGS84 GeoPackage intermediate and reprojects it to EPSG:3857 with DuckDB spatial in `_mercator_geoms`, so the Mercator projection survives.
- Zip sources are extracted before reading, because GDAL `/vsizip` keys off a `.zip` suffix that the cached filename does not have.
- The raster extension v2.0.0 is not declared, its schema conflicts with Collection-level assets (spec issues #52 and #41). Statistics still ship in core `bands`.
- COG overview depth is never pinned. `to_cog` omits `overview_level` so rio-cogeo derives it from the raster size and the 512px output blocksize, halving until the coarsest level fits inside one tile. That is OGC 21-026's `/req/optimized_geotiff/number`, which formats.md raises to a MUST and reis enforces as PTL-DAT-011. A fixed level, which this used to carry, under-builds overviews on a large raster and builds pointless ones on a raster smaller than a tile. Note the requirement reads "one tile across or down", so the bar is the shorter side, which is what rio-cogeo measures.
- A MapLibre style's PMTiles url is relative to the `styles/` directory the file sits in, so it is `../name.pmtiles`, never `./name.pmtiles`. The `./` form resolves to `styles/name.pmtiles`, which does not exist, and the style then loads no tiles and renders an empty map. Nothing else catches this, reis does not read style bodies and the STAC validators skip style files for having no `stac_version`, so `check_styles.py` asserts every url resolves to a real file. The source key and every `layers[].source` are `data` per formats.md, while `source-layer` stays the tippecanoe layer name.
- The thumbnail is painted from the DEFAULT style, meaning the variant listed first in `style.variants`, because core.md requires exactly that and core.md also says the default is listed first. `stacio` passes `default_variant` into the thumbnail context and `thumbnails.py` only reaches for the category palette when that variant is in `CATEGORICAL_VARIANTS`. So a Collection that wants a category-coloured preview leads with `categorical`, it does not keep a flat `default` in front of it. Previously the thumbnail branched on `category_field` alone and three Collections shipped previews with zero pixels in common with their own default style.
- tippecanoe records both `--name` and the verbatim command line in the archive metadata, so it runs with `cwd` set to the Collection directory and bare filenames. Passing absolute paths ships the builder's home directory inside every published `.pmtiles`.
- A nested Collection's STAC `id` is its full POSIX path from the catalog root, `boundaries/us-counties`, not the leaf segment. Filenames still use the leaf, a slash cannot appear in one. Nothing validates this, reis has no id rules and the profile schema has no id constraint, so it is easy to regress.
- The `source` asset does not carry the `data` role. core.md scopes `data` to the primary GeoParquet, COG, or Parquet and says the cloud-native asset is primary while the rest are alternates, so rolling a zipped Shapefile `data` leaves a client filtering on that role unable to tell which asset is canonical.
- The Boston, San Francisco, and Eurostat sources are live endpoints (`stable: false`), so they carry no `source`-role Asset and each README says so. Pinning a checksum on a live query URL guarantees a validator failure once upstream changes, and formats.md scopes the rule to an original that is directly downloadable rather than an API. `fetch` still refetches them instead of reusing the cache, because the canonical Asset is converted from those bytes and a stale cached copy would publish a `data` Asset that no longer matches upstream. That is how spec issue #80 happened, and the build's own validator cannot catch it, since the local-only reader skips remote assets. The DataSF URL also carries `$order=:id` so the 5k window does not reshuffle between fetches.

## Validation

`validate` runs after each catalog unless `--only` or `--no-validate` is set. It
calls reis, the canonical Portolan validator, and fails the build on any error
finding. Warnings and infos print without failing.

Four passes run. The metadata pass checks the Portolan rules. The structural
pass checks STAC 1.1.0 core validity and degrades to a warning when its
schemas are unreachable. The schema pass validates every object against the
working-copy schema at `../../stac/json-schema/v0.1.0/schema.json`, injected
so the build tests this repo's schema rather than the published one. The data
pass reads the built assets and checks checksum, size, format, COG internal
overviews, COG band statistics including valid percent, and GeoParquet ordering,
statistics, and row-group size, through a local-only reader that skips remote
source assets so the build stays offline.

Because the build skips remote assets, the remote `source` checksums are only
proven by running reis directly, without the adapter. Do that before publishing a
rebuild.

```bash
uv run --with "reis[data] @ git+https://github.com/portolan-sdi/reis.git" \
  reis check --data examples/catalog/reference
```

The build is clean apart from eight infos, which are expected and terminal. Do
not try to make the output silent.

- `PTL-PRO-002` on all eight Collections, a missing `canonical` link. core.md
  makes `canonical` a conditional MUST, owed only when the upstream publishes its
  own STAC catalog. None of these eight upstreams does, checked directly and
  against all of STAC Index, so the condition never triggers and there is no URL
  to point at. reis scores it info precisely because metadata cannot settle the
  question. Inventing a link would be worse than the finding.

A ninth finding used to be terminal and no longer is. `PTL-DAT-005` warned on
`netherlands-provinces` because reis derived its comparison bbox by reprojecting
only the four corners of the asset's native EPSG:28992 bbox, which is not a bound
under a non-affine projection. Filed as portolan-sdi/reis#26 and fixed in
portolan-sdi/reis#28, which brackets the reprojected extent between a densified
outer bound and an inner bound instead. Collections that preserve a projected
source CRS validate cleanly from reis
`7bb322961dc7fa4d49744604ee227346561f7f64` onward.

reis's live-hosting pass (`--live`, PTL-LIV) is deliberately not wired in. It
probes the servers behind absolute `https` asset hrefs. The catalog does have
eight of those, one `source` asset per Collection, so the pass would find
targets. It skips them anyway, because `reis/src/reis/live.py` exempts any
`source` or `alternate` asset on the grounds that the publisher does not run
that server. So the pass has nothing left to probe until the catalog is
published at a real base URL and its own relative hrefs become absolute.
Revisit then.

Worth knowing that the exemption is reis's own invention. core.md's Data Storage
section says "Servers MUST support range requests" and requires CORS with
`Access-Control-Expose-Headers`, unqualified, with no carve-out for upstream
servers. Measured against the eight upstream sources, two ignore `Range`
entirely, four send no CORS header, and none sends
`Access-Control-Expose-Headers`. Nothing the generator can fix, those are third
party servers. The spec should scope those MUSTs to assets the publisher hosts.

reis is a pinned git dependency in `build.py`'s PEP 723 header. Bumping the
Portolan schema is a coordinated change across this repo and reis, update the
local schema, regenerate the reference catalog, re-vendor fixtures into reis,
then bump the reis pin here.

## Conventions

- Use the official STAC names everywhere, Catalog, nested Catalog, Collection, Item, Asset. Never write "dataset".
- Generated prose in `README.md` and `AGENTS.md` avoids em dashes, colons, and semicolons, matching the project writing style. Keep new generated copy the same.
- Keep the generator dependency-light, small modules each with one responsibility. Prefer the manifest and standard FOSS tools over new Python dependencies. When code moves between modules, keep imports explicit, no wildcard imports.
