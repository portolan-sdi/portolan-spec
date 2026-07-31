# Changelog

All notable changes to the Portolan specification are recorded here. The Portolan
STAC profile keeps its own changelog in [`stac/CHANGELOG.md`](stac/CHANGELOG.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
under the pre-1.0 bump policy described in the [README](README.md#versioning).

## Unreleased

### Changed

- **Assets** (PORTO-CORE-028): `file:size` and `file:checksum` drop from MUST to
  SHOULD. A catalog that describes data it does not host often cannot produce a
  checksum, so the old MUST left it a choice between failing conformance and
  publishing a fabricated value (#112).
- **Assets** (PORTO-CORE-030): the publish-time regeneration rule is restated as
  an outcome. Any `file:size` and `file:checksum` an asset carries MUST match the
  bytes its `href` resolves to, whenever and however they were written. Its
  enforcement moves from `process` to `validator`, since a data pass can check it.
- **Assets** (PORTO-CORE-029): reworded to govern a `file:checksum` where one is
  present. Multihash encoding is still required, unchanged in force.
- **Requirements manifest**: still 115 requirements, now 83 MUST, 18 SHOULD, and
  14 MAY.

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
