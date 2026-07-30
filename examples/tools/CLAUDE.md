# examples/tools/, Portolan reference catalog generator

This directory holds the generator, a minimal open-source tool that turns YAML
manifests into complete, v0.1-conformant Portolan STAC catalogs. It is a small
set of plain sibling modules run through the `build.py` entrypoint. The manifests
it reads and the catalog it produces live one level up under `examples/`. Read
this before editing the generator.

## Layout

The generator is a set of modules under `examples/tools/`, each owning one
responsibility. `build.py`, `check_catalogs.py`, `publish_catalogs.py`, and the
files under `tests/` are `uv run` entrypoints and carry a PEP 723 header. The
rest are plain modules, and `build.py` bootstraps `sys.path` with its own
directory so they import as flat names. `build.py` and `publish_catalogs.py`
import nothing from the modules beside them, so they stay runnable on their own.

`check_catalogs.py` is the deliberate exception. It is an entrypoint and a shared
module both, `build.py` imports `load_baseline` from it and `validate.py` imports
`apply_baseline`, so the build-time and the gate-time paths read one baseline
implementation rather than two that can drift. It declares no dependencies of its
own and runs on the standard library alone, so importing it costs nothing and its
empty PEP 723 header stays valid. Keep it that way, a dependency added there
would land on every importer.

| Module | Responsibility |
|--------|----------------|
| `build.py` | Entrypoint. PEP 723 header, argparse, `main`, resolves paths from the repo root |
| `config.py` | Static constants, extension URIs, media types, GDAL band-type map, palette |
| `common.py` | Shared helpers, subprocess runner, checksums, value formatting |
| `fetch.py` | Downloads sources into `.cache` and unpacks zipped shapefiles |
| `convert.py` | Format conversions, vector to GeoParquet, raster to COG, CSV to Parquet |
| `mosaic.py` | The `raster-mosaic` path. Reads an upstream STAC search, emits one Item per scene with the COG left upstream, writes the `items.parquet` mirror, the `minimal.json` bbox index, and the mosaic thumbnail |
| `derivatives.py` | PMTiles tiles and data-driven MapLibre styles |
| `thumbnails.py` | Web Mercator preview rendering over the tile basemap fetched by `tiles.py` |
| `tiles.py` | XYZ basemap tile fetch and mosaic for thumbnails |
| `stacio.py` | STAC assembly, manifest, providers, assets, links, sidecars, catalog builders |
| `validate.py` | Thin adapter over rashid, the canonical validator. Runs its metadata, structural, schema, and data passes over the built catalog |
| `check_catalogs.py` | Entrypoint, and the shared module holding the baseline loader and matcher. Runs rashid over every built catalog tree, reading the rashid pin out of `build.py`'s PEP 723 header. Data pass full unless a baseline narrows it with `data_scope`, findings gated against `../expected-findings/<stem>.json` |
| `publish_catalogs.py` | Entrypoint. Uploads a built catalog to Source Cooperative, and tears a pull request's preview down |
| `tests/` | Standalone `uv run` checks, `check_compliance.py`, `check_web_output.py`, `check_validate.py`, `check_tiles.py`, `check_thumb_geoms.py`, `check_thumbnails.py`, `check_cog.py`, `check_fetch.py`, `check_styles.py`, `check_mosaic.py`, `check_items_parquet.py`, and `check_baseline.py`, plus `run_all.py` which runs the lot |

Inputs and outputs live under `examples/`, not here.

| Path | What it is |
|------|------------|
| `../manifests/*.yaml` | Inputs. One file describes one whole catalog. Named after the `id` it declares |
| `../catalog/<stem>/` | Output. One STAC tree per manifest, named after the file stem, which equals the catalog id |
| `../.cache/` | Downloaded upstream sources, git-ignored, safe to delete |

## Running it

```bash
uv run examples/tools/build.py                                # build every manifest
uv run examples/tools/build.py --catalog portolan-reference   # one manifest by stem
uv run examples/tools/build.py --only boundaries/us-counties  # one Collection, skips validation
```

`uv` reads the PEP 723 header at the top of `build.py` and resolves the Python
deps (pyyaml, duckdb, jsonschema, pyarrow, rasterio, rio-cogeo, and the pinned
geoparquet-io) on the fly. The whole generator, data path and thumbnails
alike, runs on DuckDB spatial, rasterio, and rio-cogeo, none of it shells out
to the GDAL CLI, so the only prerequisites on PATH are `tippecanoe` and `uv`.

The test scripts run the same way, and `run_all.py` runs all of them, reporting
every result rather than stopping at the first failure. That is what CI runs.

```bash
uv run examples/tools/tests/run_all.py           # all of them
uv run examples/tools/tests/check_compliance.py  # or one at a time
uv run examples/tools/tests/check_web_output.py
uv run examples/tools/tests/check_validate.py
uv run examples/tools/tests/check_tiles.py
uv run examples/tools/tests/check_thumb_geoms.py
uv run examples/tools/tests/check_thumbnails.py
uv run examples/tools/tests/check_cog.py
uv run examples/tools/tests/check_fetch.py
uv run examples/tools/tests/check_styles.py
```

Publishing a built catalog to Source Cooperative needs `s5cmd` on PATH as well,
and credentials for the Portolan repository in the environment or an AWS
profile. Always dry-run first, the sync deletes what the local tree does not
have.

```bash
uv run examples/tools/publish_catalogs.py --list                     # the publishable stems
uv run examples/tools/publish_catalogs.py --catalog portolan-reference --dry-run
uv run examples/tools/publish_catalogs.py --catalog portolan-reference
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
- `kind`. One of `vector`, `raster`, `raster-mosaic`, `tabular`. Selects the conversion path.
- `geometry`. `polygon`, `point`, or `line`. Vector only, drives style and thumbnail paint.
- `title`, `description`, `keywords`, `license`, `attribution?`.
- `license_url?`. Required only when `license` is `other`. The URL of the license text. The generator emits the mandatory `rel: license` link from it.
- `source`. `{url, media_type, title, layer?, stable}`. The true original upstream file, and for `raster-mosaic` the STAC search endpoint the Items are read from, which the generator explicitly refuses to treat as a downloadable original. `stable: false` marks a live endpoint, and `raster-mosaic` must set it or the build fails.
- `providers`. List of `{name, url, roles}`. Roles are `producer`, `licensor`, `processor`, `host`.
- `provenance`. `{via?, canonical?, updated?}`.
- `temporal`. `[start, end_or_null]`.
- `thumbnail_bbox?`. `[minx, miny, maxx, maxy]`. Frames the preview only, not the data. Use it for antimeridian-spanning data.
- `derivatives`. `{pmtiles, thumbnail, minimal_json}`. Booleans that toggle the PMTiles, the thumbnail, and the `minimal.json` bbox and href index. `minimal_json` is read on the `raster-mosaic` path only and defaults off.
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

`vector`, `raster`, and `tabular` kinds download the source into `.cache` and
produce a cloud-native canonical `data` Asset. `raster-mosaic` mirrors remote
Items without downloading. When the manifest marks the source `stable: true`, it
also emits a `source`-role Asset that points at the upstream URL with the real
`file:size` and multihash `file:checksum` of the fetched file. A `stable: false`
source, meaning a live endpoint, is referenced by URL in the sidecars only,
because pinned checksums on bytes the catalog does not control are guaranteed to
rot. `add_source_asset` is the single gate.

- `vector`. `to_geoparquet` converts with DuckDB spatial, preserving the source CRS or the manifest `output_crs`, and also builds a WGS84 GeoPackage for the bbox, the PMTiles feed, the thumbnail, and style sampling. It then writes the canonical asset as a web-optimized GeoParquet 2.0 file with geoparquet-io's web profile (native geometry type, per row group GeospatialStatistics, a retained covering bbox column for page-level pruning, a Parquet page index, Hilbert ordering, and byte-targeted fetch-sized row groups). Derivatives read the WGS84 GeoPackage, not the 2.0 output. Optional PMTiles come from a DuckDB GeoJSONSeq export into tippecanoe, with a web-map-links `pmtiles` link. Optional MapLibre styles are authored by `author_styles` from the real field values and read the PMTiles. The GeoParquet `data` asset also carries `table:columns` from a DuckDB `DESCRIBE`, geometry column included, and `proj:code` derived from the real output CRS, declaring the table and projection extensions.
- `raster`. `to_cog` builds the COG with rasterio, preserving the source CRS or warping to the manifest `output_crs`. Band statistics come from rasterio and numpy and go in STAC 1.1 core `bands`, minimum, maximum, mean, stddev, and valid percent, and `proj:code` carries the real output CRS through the projection extension. The same values are embedded as GDAL `STATISTICS_*` band tags, which is where rashid reads them. Overview depth is left to rio-cogeo rather than pinned, see the gotcha below.
- `raster-mosaic`. `mosaic.py` fetches an upstream STAC search response and emits one Item per scene, each carrying the upstream COG href unchanged. Nothing is downloaded and nothing is converted, so the source must be marked `stable: false` and `stacio` raises if it is not. Per scene it costs two HEADs, for the COG and the thumbnail sizes, and one ranged read of the coarsest internal overview, which serves both the `bands` statistics and the mosaic thumbnail. Those statistics are flagged `approximate` because an overview is not the full raster. The Collection also gets an `items.parquet` mirror with the `collection-mirror` role, Hilbert-sorted with an explicit row-group size, and a `minimal.json` bbox-and-href index with the `metadata` role for client-side mosaic viewers. `file:checksum` is omitted on every remote asset, which is the residual non-conformance the baseline accepts.
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
- COG overview depth is never pinned. `to_cog` omits `overview_level` so rio-cogeo derives it from the raster size and the 512px output blocksize, halving until the coarsest level fits inside one tile. That is OGC 21-026's `/req/optimized_geotiff/number`, which formats.md raises to a MUST and rashid enforces as PTL-DAT-011. A fixed level, which this used to carry, under-builds overviews on a large raster and builds pointless ones on a raster smaller than a tile. Note the requirement reads "one tile across or down", so the bar is the shorter side, which is what rio-cogeo measures.
- A MapLibre style's PMTiles url is relative to the `styles/` directory the file sits in, so it is `../name.pmtiles`, never `./name.pmtiles`. The `./` form resolves to `styles/name.pmtiles`, which does not exist, and the style then loads no tiles and renders an empty map. Nothing else catches this, rashid does not read style bodies and the STAC validators skip style files for having no `stac_version`, so `check_styles.py` asserts every url resolves to a real file. The source key and every `layers[].source` are `data` per formats.md, while `source-layer` stays the tippecanoe layer name.
- The thumbnail is painted from the DEFAULT style, meaning the variant listed first in `style.variants`, because core.md requires exactly that and core.md also says the default is listed first. `stacio` passes `default_variant` into the thumbnail context and `thumbnails.py` only reaches for the category palette when that variant is in `CATEGORICAL_VARIANTS`. So a Collection that wants a category-coloured preview leads with `categorical`, it does not keep a flat `default` in front of it. Previously the thumbnail branched on `category_field` alone and three Collections shipped previews with zero pixels in common with their own default style.
- tippecanoe records both `--name` and the verbatim command line in the archive metadata, so it runs with `cwd` set to the Collection directory and bare filenames. Passing absolute paths ships the builder's home directory inside every published `.pmtiles`.
- A nested Collection's STAC `id` is its full POSIX path from the catalog root, `boundaries/us-counties`, not the leaf segment. Filenames still use the leaf, a slash cannot appear in one. Nothing validates this, rashid has no id rules and the profile schema has no id constraint, so it is easy to regress.
- The `source` asset does not carry the `data` role. core.md scopes `data` to the primary GeoParquet, COG, or Parquet and says the cloud-native asset is primary while the rest are alternates, so rolling a zipped Shapefile `data` leaves a client filtering on that role unable to tell which asset is canonical.
- The Boston, San Francisco, and Eurostat sources are live endpoints (`stable: false`), so they carry no `source`-role Asset and each README says so. Pinning a checksum on a live query URL guarantees a validator failure once upstream changes, and formats.md scopes the rule to an original that is directly downloadable rather than an API. `fetch` still refetches them instead of reusing the cache, because the canonical Asset is converted from those bytes and a stale cached copy would publish a `data` Asset that no longer matches upstream. That is how spec issue #80 happened, and the build's own validator cannot catch it, since the local-only reader skips remote assets. The DataSF URL also carries `$order=:id` so the 5k window does not reshuffle between fetches.

## Validation

`validate` runs after each catalog unless `--only` or `--no-validate` is set. It
calls rashid, the canonical Portolan validator, and fails the build on any error
finding. Warnings and infos print without failing.

Four passes run. The metadata pass checks the Portolan rules. The structural
pass checks STAC 1.1.0 core validity and degrades to a warning when its
schemas are unreachable. The schema pass validates every object against the
working-copy schema at `../../stac/json-schema/v0.1.0/schema.json`, injected
so the build tests this repo's schema rather than the published one. The data
pass reads the built assets and checks checksum, size, format, COG internal
overviews, COG band statistics including valid percent, and GeoParquet ordering,
statistics, and row-group size, through rashid's `LocalOnlyReader`, which skips
remote source assets so the build stays offline. That class used to be a private
copy in `validate.py`. rashid ships an equivalent one plus a
`data_reader_factory` hook as of PR #87, so the copy was deleted and the upstream
one wired in. `tests/check_validate.py` asserts the wiring, because dropping it
would silently start streaming every remote asset.

Because the build skips remote assets, the remote `source` checksums are only
proven by running rashid directly, without the adapter. Do that before publishing a
rebuild.

```bash
uv run --with "rashid[data] @ git+https://github.com/portolan-sdi/rashid@8d9e11f2b742e2873a2f397a182c8e1aace07dcc" \
  rashid check --schema examples/catalog/portolan-reference
```

The build is clean apart from eight infos, which are expected and terminal. Do
not try to make the output silent.

- `PTL-PRO-002` on all eight Collections, a missing `canonical` link. core.md
  makes `canonical` a conditional MUST, owed only when the upstream publishes its
  own STAC catalog. None of these eight upstreams does, checked directly and
  against all of STAC Index, so the condition never triggers and there is no URL
  to point at. rashid scores it info precisely because metadata cannot settle the
  question. Inventing a link would be worse than the finding.

A ninth finding used to be terminal and no longer is. `PTL-DAT-005` warned on
`netherlands-provinces` because rashid derived its comparison bbox by reprojecting
only the four corners of the asset's native EPSG:28992 bbox, which is not a bound
under a non-affine projection. Filed as portolan-sdi/rashid#26 and fixed in
portolan-sdi/rashid#28, which brackets the reprojected extent between a densified
outer bound and an inner bound instead. Collections that preserve a projected
source CRS validate cleanly from rashid
`7bb322961dc7fa4d49744604ee227346561f7f64` onward.

rashid's live-hosting pass (`--live`, PTL-LIV) is deliberately not wired in. It
probes the servers behind absolute `https` asset hrefs. The catalog does have
eight of those, one `source` asset per Collection, so the pass would find
targets. It skips them anyway, because `rashid/src/rashid/live.py` exempts any
`source` or `alternate` asset on the grounds that the publisher does not run
that server. So the pass has nothing left to probe until the catalog is
published at a real base URL and its own relative hrefs become absolute.
Revisit then.

Worth knowing that the exemption is rashid's own invention. core.md's Data Storage
section says "Servers MUST support range requests" and requires CORS with
`Access-Control-Expose-Headers`, unqualified, with no carve-out for upstream
servers. Measured against the eight upstream sources, two ignore `Range`
entirely, four send no CORS header, and none sends
`Access-Control-Expose-Headers`. Nothing the generator can fix, those are third
party servers. The spec should scope those MUSTs to assets the publisher hosts.

rashid is pinned in `build.py`'s PEP 723 header. It currently points at the exact
merge commit `8d9e11f2b742e2873a2f397a182c8e1aace07dcc`, which is
[PR #87](https://github.com/portolan-sdi/rashid/pull/87), rather than at a PyPI
range, because the `--data-scope` support that catalog validation now depends on
is not in any release. `v0.1.3` predates the merge. A commit pin rather than
`@main` keeps the build reproducible. **Return this to a version range once it
ships.**

There is a second pin, in `tests/check_validate.py`'s own PEP 723 header, because
that script runs standalone rather than through `build.py`. Move both together.
`check_catalogs.py` has no pin of its own, it reads `build.py`'s.

Bumping the Portolan schema is a coordinated change across this repo and rashid,
update the local schema, regenerate the reference catalog, re-vendor fixtures into
rashid, then bump the rashid pin here.

### The expected-findings baseline

`portolan-reference` is fully conformant and stays at zero tolerance.
`naip-mosaic` cannot be, because it publishes metadata for COGs hosted by the
Microsoft Planetary Computer and `file:checksum` on bytes this project never reads
is unobtainable rather than merely unimplemented. So `check_catalogs.py` gates that
catalog against `../expected-findings/naip-mosaic.json` instead.

A baseline is not a mute button, and `tests/check_baseline.py` asserts that.

- A catalog with no baseline file keeps zero tolerance. That is where
  `portolan-reference` sits, and adding a catalog does not change it.
- A rule the baseline does not name fails the gate, so a new defect cannot hide
  behind a known gap.
- A named rule over its `max_count` ceiling fails, so a known gap growing is still
  a regression.
- Infos never fail, matching the reference catalog's eight terminal `PTL-PRO-002`
  findings.
- Every entry carries a `why` and an `issue`, so a reader can tell an accepted gap
  from a silenced one without leaving the file.

`naip-mosaic` accepts exactly two rules, `PTL-AST-003` at a ceiling of 2000 and
`PTL-SCH-001` at 1000. The real counts are 1848 and 924, summing to the 2772 the
gate reports. Note the asymmetry, `PTL-AST-003` is reported per asset so it fires
twice per Item, once for the scene COG and once for the referenced upstream
thumbnail, while `PTL-SCH-001` is reported per file so it fires once per
`item.json` however many of that Item's assets are short the property. Getting that
backwards inflates the expected total to 3696.

### Why naip-mosaic runs a narrowed data scope

`naip-mosaic` describes 1.86 TB of COGs it does not host. rashid's default data
pass streams every asset in full, even when there is no checksum to hash, because
size is a byte counter and format detection reads the leading bytes. Extrapolating
a 2-scene timing of 5 m 56 s puts a full pass on the order of 45 hours. That is
not a CI job.

**This was filed and answered inside a day, and the answer is in the branch.**
[rashid#86](https://github.com/portolan-sdi/rashid/issues/86) was filed from this
work, framed as a use case rather than a defect.
[PR #87](https://github.com/portolan-sdi/rashid/pull/87) merged 2026-07-30 citing
it, adding `--data-scope local`. It runs every data rule against assets inside the
catalog tree and treats a remote href as unfetchable, exactly as an `s3` href
already was. It also adds `PTL-DAT-016` to the runner's data-rule set, which had
omitted it.

So the baseline now carries `"data_scope": "local"` rather than a boolean off
switch, and `check_catalogs.py` passes `--data-scope local`. A boolean selecting
between three behaviours would have been worse than a named scope. The field
absent means the full default pass, which is where `portolan-reference` sits.
`DATA_SCOPES` is a closed set, so a typo fails loudly instead of silently widening
the pass.

**Narrowing the scope is not skipping the pass.** The Collection's own
`items.parquet` is now fully checked, `PTL-DAT-001` checksum, `PTL-DAT-002` size,
`PTL-DAT-006` spatial ordering, `PTL-DAT-016` row-per-item parity and the rest. On
the built tree the result is identical to the old `--no-data` run, 2772 errors
across 927 files, so adopting it cost nothing and gained the local rules. Verified
by mutation, truncating `items.parquet` by 2000 bytes in a temp copy makes the gate
fail on `PTL-DAT-001` and `PTL-DAT-002`, neither of which is in the baseline.

What stays unchecked is the bytes of the 1848 remote assets. No gate here has ever
read those, and `PTL-AST-003` in the baseline already records them as unverifiable.

`tests/check_items_parquet.py` predates the scope and its old docstring claimed to
exist because the data pass was off. That is no longer true and the docstring is
corrected. It stays because it exercises `write_items_parquet` directly over a
synthetic fixture, so a writer regression fails fast without a rebuild and without
invoking rashid. The gate proves the artifact, that test proves the code.

One thing the pass still cannot reach. The embedded COG statistics MUSTs,
`PORTO-FMT-026` through `029`, are unverifiable for a mirror by construction.
Upstream NAIP COGs carry no `STATISTICS_*` band tags, this catalog publishes
approximate values read from each scene's coarsest overview into STAC core `bands`
instead, and no configured gate sees the difference. That gap stays deliberately
unbaselined, because an accepted entry for a rule that never fires would be a
false record.

## What CI runs, and why it is split in three

The example catalogs used to be checked by nothing, so they could drift out of
conformance between rebuilds unnoticed. Two workflows cover that now, split on
whether the check needs the network, and a third publishes what they check.

`.github/workflows/examples-checks.yaml` runs `tests/run_all.py` on every push
and pull request, with no path filter. Every check in there is offline and
deterministic and the suite takes about twelve seconds, so there is no reason to
filter, and an unfiltered workflow is the only kind that can be a required
status check. A path-filtered one stays pending on the PRs it skips.

`.github/workflows/catalog-upstream.yaml` runs `examples/tools/check_catalogs.py`
weekly and on demand. That is the one that refetches the upstream sources and
proves their `file:size` and `file:checksum`. It is not a PR gate on purpose. It
depends on five third-party servers, so gating merges on it would block work
whenever one of them is briefly down, which says nothing about the PR. A failure
opens an issue instead, or comments on the open one. It discovers catalogs by
globbing built trees under `examples/catalog/`, and this run never builds one
itself, so since `naip-mosaic` stopped being committed it no longer covers that
catalog at all.

`.github/workflows/publish-catalogs.yaml` builds each manifest and uploads the
result to the Portolan repository on Source Cooperative with
`examples/tools/publish_catalogs.py`, so an example is readable at a real URL rather
than only in git. It runs when a manifest, a generator module, or a committed
rebuild lands on main, on every pull request, and on demand for one catalog or
as a dry run. Transfers go through `s5cmd`, which handles a tree of many small
JSON files far better than the AWS CLI. Nothing reaches a public URL
unvalidated, the same `check_catalogs.py` gate runs between the build and the
upload, and afterwards the published `catalog.json` is refetched over HTTPS and
its `id` checked. Its path triggers still fire for `naip-mosaic` through
`examples/manifests/**` and `examples/**/*.py`, since that catalog is no longer
committed the `examples/catalog/**` trigger simply has nothing left to match
for it.

The prefix taxonomy is not ours. `CartoDB/portolan-pipeline` already publishes
into the same Source Cooperative repository, so `publish_catalogs.py`
reimplements its scheme from `docs/branch-versioning.md` rather than inventing a
second one that would sit confusingly beside it. The layout is
`<catalog id>/<namespace>`.

| git context | published prefix |
| --- | --- |
| push to `main` or `master` | `<id>/main/` |
| push to any other branch | `<id>/branches/<slug>/` |
| pull request N | `<id>/PRs/N/`, deleted when it closes |

Three details of that scheme are load bearing and easy to get wrong. The key is
the catalog **id** from the manifest, not the manifest file name. Every manifest
is named after the id it declares, so `portolan-reference.yaml` publishes to
`portolan-reference/` and the two never drift. A slug collapses every run
of characters outside `[a-z0-9._-]` to one dash, so `feat/x` becomes `feat-x`
and stays a single path segment. And the default-branch test runs on the raw
ref, so a branch named `Main` lands in `branches/main` rather than overwriting
the canonical catalog. That last one reads like an upstream oversight and is the
safer behaviour, so it is matched deliberately. The ground-truth cases from
their `tests/test_context.py` all pass against our implementation.

A pull request from a fork is skipped rather than run, since GitHub withholds
secrets there and the build would burn its full runtime only to fail at the
upload. That costs `naip-mosaic` more than the other catalogs, a fork's pull
request gets no validation of it whatsoever, where the committed tree used to be
at least readable in the diff. `.github/workflows/teardown-previews.yaml` deletes a PR's previews when
it closes, guarded so that only a numeric PR number resolving to a path that
still contains `/PRs/<n>/` is ever deleted.

A published preview is also commented onto the pull request, so review looks at
a rendered catalog rather than at a diff of Parquet, COG, and PMTiles. The
comment is marked `<!-- portolan-publish:<stem> -->` and rewritten in place, one
per catalog, so ten pushes leave one comment rather than ten. `review_urls` in
`publish_catalogs.py` derives both links from the public URL the run actually
uploaded to rather than reassembling them from the parts, so a link cannot point
at a prefix this run did not write. The STAC Browser form drops the scheme,
`https://browser.portolan-sdi.org/#/external/data.source.coop/...`, and the file
browser serves the same path from the bare `source.coop` domain.

`check_catalogs.py` reads the rashid requirement out of `build.py`'s PEP 723
header with `tomllib`, so the validator that checks a catalog is the validator
that built it and there is no second pin to drift. It is generic over every tree
under `examples/catalog/`, so a new manifest is covered as soon as its output is
built. Its gate is errors and warnings, since rashid's own exit code fires
on errors alone and a warning in a reference example is a real defect. The eight
infos above are advisory and do not fail it.

Two known gaps. `check_catalogs.py` validates against the profile schema bundled
in the rashid wheel, while `validate.py` injects the working copy under `stac/`,
so a change to `stac/json-schema/` is proven by the build rather than by CI. And
`check_validate.py` is hardcoded to the `portolan-reference` tree, so a second catalog
gets weekly coverage immediately but per-PR coverage only once that script is
generalized.

## Conventions

- Use the official STAC names everywhere, Catalog, nested Catalog, Collection, Item, Asset. Never write "dataset".
- Generated prose in `README.md` and `AGENTS.md` avoids em dashes, colons, and semicolons, matching the project writing style. Keep new generated copy the same.
- Keep the generator dependency-light, small modules each with one responsibility. Prefer the manifest and standard FOSS tools over new Python dependencies. When code moves between modules, keep imports explicit, no wildcard imports.
