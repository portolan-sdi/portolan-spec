# Changelog

All notable changes to the Portolan specification are recorded here. The Portolan
STAC profile keeps its own changelog in [`stac/CHANGELOG.md`](stac/CHANGELOG.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
under the pre-1.0 bump policy described in the [README](README.md#versioning).

## Unreleased

### Added

- `PORTO-FMT-044`: a vector collection SHOULD document its columns with the
  STAC [table](https://github.com/stac-extensions/table) extension, carrying
  `table:columns` on the collection or on the GeoParquet asset. The same SHOULD
  already covered tabular collections (`PORTO-FMT-037`); nothing asked a vector
  collection for its schema, so a catalog could publish a hundred attribute
  columns that a client could only discover by reading the Parquet footer.

### Changed

- Rewrote the golden-example documentation to the standard in
  [`specs/best-practices/documentation.md`](specs/best-practices/documentation.md)
  (#81). Every Collection README now opens with a researched narrative and
  numbers, carries a tested Quick Start, a described schema table, suggested
  uses, and candid limitations, and every AGENTS.md is dataset-specific with
  join keys, quirks, CRS consequences, and tested query recipes. The prose
  lives in the manifest as per-collection markdown templates with generated
  `{{placeholder}}` blocks, so structure varies by Collection while counts,
  schemas, and code cannot drift from the built assets. Catalog-level READMEs
  became collections tables. A new `check_docs.py` executes every code block
  in the committed docs, and `build.py --docs-only` regenerates documentation
  without refetching data.
- The `boundaries/netherlands-provinces` example now mirrors its upstream ISO
  19115 record from the Nationaal Georegister as a `metadata`-role asset.
- Corrected example metadata found during research for #81. The
  `raster/sample-cog` license is CC0-1.0, matching rasterio's dedication of
  its test images, its temporal extent starts at the Landsat 7 launch instead
  of a placeholder, the Natural Earth temporal extents match the May 2022
  5.1.x releases, and the Eurostat join documentation targets `ISO_A2_EH`
  with the EL and UK remaps, the raw `ISO_A2` join silently dropped France,
  Norway, and Kosovo.

## 0.1.0 - 2026-07-27

First tagged release, consolidating the specification from a working draft into a
versioned standard. A catalog declares this version by carrying
`https://schemas.portolan-sdi.org/portolan/v0.1.0/schema.json` in `stac_extensions`.

### Added

- **Normative core** ([`specs/portolan/core.md`](specs/portolan/core.md)): catalog
  structure, conformance and versioning, catalogs, collections, items, assets,
  links, human-readable titles, bounding boxes and spatial extent, temporal
  metadata, data storage, providers, source provenance, license, `AGENTS.md`,
  `README.md`, metadata, and visualization.
- **Format requirements** ([`specs/portolan/formats.md`](specs/portolan/formats.md)):
  vector as GeoParquet with PMTiles, raster as COG, non-geospatial tabular data as
  Parquet, and point clouds as COPC.
- **Requirements manifest**
  ([`specs/portolan/requirements.yaml`](specs/portolan/requirements.yaml)): 115
  requirements (84 MUST, 17 SHOULD, 14 MAY), each with a stable ID, a severity, an
  enforcement mode, and a verbatim quote from the prose.
  [`specs/tools/check_requirements.py`](specs/tools/check_requirements.py) anchors every
  normative keyword in the prose to a manifest entry, and CI fails on drift.
- **Conformance model**: the versioned schema URI is the single signal of
  specification version, declared on catalogs and collections only, with items
  inheriting from their collection. No separate version property exists, no
  `portolan:`-prefixed fields are defined, and `versions.json` is a tooling artifact
  rather than a catalog requirement. Dataset versioning uses the STAC version
  extension. Conformance means passing the validator, in three separable passes:
  STAC structural, Portolan metadata, and Portolan data.
- **Collection mirrors** (PORTO-FMT-040 through 043): a raster collection that models
  scenes as items SHOULD publish a stac-geoparquet mirror of those items at
  `items.parquet` in the collection root, registered as a collection-level asset with
  media type `application/vnd.apache.parquet` and the role `collection-mirror`. The
  mirror reproduces the collection's items exactly at publish time, one row per item,
  and the GeoParquet storage rules bind it as they bind any other vector asset.
- **Item-level assets** for multi-scene raster collections, so each scene carries its
  own data rather than collapsing into collection-level assets.
- **Optimized GeoTIFF conformance**: a COG must meet OGC 21-026's
  `/req/optimized_geotiff` requirements class, including square viewport-sized
  internal tiles, internal reduced-resolution overviews, and GeoTIFF keys on the
  full-resolution IFD.
- **Partition binding**: a collection carrying any `partition:*` field declares the
  incubating partition extension and carries `partition:scheme`, `partition:keys`,
  and `partition:glob`, where `partition:glob` is the normative bulk-access path.
- **Portolan STAC profile** ([`stac/`](stac/)): a JSON Schema for the structural
  requirements checkable from STAC JSON alone, plus the normative registry of reused
  STAC extensions. See [`stac/CHANGELOG.md`](stac/CHANGELOG.md).
- **Best practices** ([`specs/best-practices/`](specs/best-practices/)),
  non-normative: catalog philosophy, documentation guidance for `README.md` and
  `AGENTS.md`, the catalog grader, styling, and conversion defaults.
- **Incubating specs** ([`specs/incubating/`](specs/incubating/)): raster styling,
  point clouds, GeoTIFF statistics headers, and STAC-GeoParquet.
- **Reference catalogs** ([`examples/`](examples/)) with the generator that builds
  them, converting vector data through DuckDB and rasters through rasterio and
  rio-cogeo, rendering thumbnails and PMTiles without a GDAL CLI, and validating
  every build with [rashid](https://github.com/portolan-sdi/rashid).
- **Schema publishing** at `schemas.portolan-sdi.org`, deployed from the tracked
  schema versions on each release, with portolan-sdi extension schemas pinned in
  `stac/portolan-extensions.json` and fetched from their source repositories at
  build time.
- **CI gates**: every PR touching normative content names its companion rashid PR or
  carries the `no-validator-change` label; the requirements manifest check anchors
  prose to IDs; the profile test suite lints markdown, pins the canonical schema URI,
  and validates the examples.
