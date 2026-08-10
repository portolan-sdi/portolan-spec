# Changelog

All notable changes to the Portolan specification are recorded here. The Portolan
STAC profile keeps its own changelog in [`stac/CHANGELOG.md`](stac/CHANGELOG.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
under the pre-1.0 bump policy described in the [README](README.md#versioning).

## Unreleased

### Added

- **GeoParquet** (PORTO-FMT-044): a validator MUST NOT fault a file for missing
  a spatial-ordering threshold its row-group count cannot express, and MAY
  measure ordering another way when the row-group tests do not apply. This
  covers the row-level measurement reis already performs on a single-row-group
  file by partitioning its rows (#127).
- **Data Storage** (PORTO-CORE-073): a validator MUST probe the servers hosting
  the catalog's own cloud-native assets and MUST NOT require upstream servers to
  satisfy the section's requirements. This writes down the carve-out reis
  already applies to `source` and `alternate` assets (#89).

### Changed

- **GeoParquet** (PORTO-FMT-006): the low-overlap and high-locality tests now
  apply only to files of five or more row groups. Both measure a fraction over
  the row groups themselves, so below five the fraction has nowhere useful to
  land: an average box under 25% of the extent is out of reach on two or three
  row groups however well the rows are sorted, and a spatially ordered
  four-row-group file was failing on that alone. The thresholds are unchanged,
  as is the rule that rows MUST be spatially ordered. The 50% skip rate for a
  10% query window now reads as the reason the threshold sits at 25% rather
  than as a second test a validator runs (#127).
- **"Item mirror" is now used consistently** (PORTO-FMT-040, PORTO-FMT-041,
  PORTO-FMT-043). The STAC-GeoParquet copy of a collection's items is now always
  referred to as an **item mirror** or **STAC-GeoParquet mirror**, leaving the
  unqualified term **mirror** to its longstanding provenance meaning: a catalog
  republishing data it did not produce. This is a wording-only change. The
  requirements are unchanged, and the upstream role value `collection-mirror` is
  unaffected (#99).
- **Data Storage** (PORTO-CORE-043, PORTO-CORE-044, PORTO-CORE-045): clarifies
  that the HTTP requirements apply to servers hosting the catalog's own
  cloud-native assets. This includes range support, `206 Partial Content`,
  `Accept-Ranges`, `Content-Length`, and CORS. Upstream originals hosted by
  third parties are out of scope, and validators do not probe those hosts. The
  requirements themselves are unchanged; this change only makes their scope
  explicit, matching the behavior already implemented in reis (#89).
- **Data Storage** (PORTO-CORE-045): the CORS requirement now names the header
  set a browser actually needs. Allowed request headers add `If-Match`,
  `If-Modified-Since`, `If-None-Match`, and `If-Unmodified-Since` next to
  `Range`, and exposed response headers add `Content-Type`. Conditional requests
  let a client revalidate a cached range instead of refetching it.
  Provider-specific headers such as `x-amz-*` and `x-goog-*` stay out of scope,
  as does versioning, which the specification does not yet define (#56).
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
- **Requirements manifest**: 116 requirements, now 85 MUST, 17 SHOULD, and
  14 MAY.
- **Default style is identified by a `default` role**
  ([`specs/portolan/core.md`](specs/portolan/core.md)): a collection with more than
  one style now MUST mark exactly one style asset with `roles: ["style", "default"]`,
  replacing the previous guidance that the default SHOULD be "listed first". STAC
  `assets` is an unordered JSON object and STAC states that asset keys carry no
  meaning a client is expected to understand, so neither order nor key is a reliable
  signal; STAC does encourage multiple roles per asset, so a second role lets a
  client find the default deterministically with no extension. `PORTO-CORE-070`
  moves from `SHOULD` to `MUST`, and the reference catalog and generator are
  updated to match.
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
