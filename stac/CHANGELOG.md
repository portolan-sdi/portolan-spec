# Changelog

All notable changes to the Portolan STAC profile will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed

- The schema no longer requires `file:size` and `file:checksum` on every asset,
  following the specification's move of both to SHOULD. Where either is present
  the schema still checks its shape, and tooling still checks the checksum's
  multihash encoding and its agreement with the bytes. A catalog that conformed
  before still conforms, so this is a non-breaking relaxation under the pre-1.0
  bump policy.
- The extension registry lists File Info as a conditional MUST, owed when an
  asset carries either field rather than on every object with assets.

## 0.1.0 - 2026-07-27

First tagged release. The schema is published at
<https://schemas.portolan-sdi.org/portolan/v0.1.0/schema.json>.

### Added

- Initial version of the Portolan STAC profile, moved from the
  `stac-portolan-extension` repository into `stac/`.
- JSON Schema covering the specification's schema-checkable structural
  requirements: non-empty titles and descriptions, titles on `child`/`item`
  links, no `self` links with relative typed structural links, `type`,
  `roles`, `file:size`, and `file:checksum` required on every asset,
  https-only absolute asset hrefs, `providers` with a producer and a
  reachable host, collection `license` never the deprecated `proprietary`,
  WGS84 bbox range validity, and the `rel: "agents"` link (with `type`) on
  Catalogs and Collections.
- Examples for a root catalog, a single-file vector collection, and a
  partitioned vector collection with an item.
- Optimized GeoTIFF conformance for rasters: a COG must meet OGC 21-026's
  Optimized GeoTIFF requirements class (`/req/optimized_geotiff`), covering square
  viewport-sized internal tiles, internal reduced-resolution overviews reducing by
  a factor of 2 to 10 until the coarsest level spans one tile, and GeoTIFF keys on
  the full-resolution IFD. The Raster section now also defines a valid COG by
  reference to OGC 21-026, the baseline `rio cogeo validate` and rasterio enforce.
- Partition binding: a collection carrying any `partition:*` field, or declaring
  the partition extension, must declare
  `https://schemas.portolan-sdi.org/incubating/partition/v1.0.0/schema.json` in
  `stac_extensions` and carry `partition:scheme`, `partition:keys`, and
  `partition:glob`. `partition:glob` is the normative bulk-access path.
- `portolan-extensions.json`: pins which portolan-sdi extension schema versions
  are published under `schemas.portolan-sdi.org/<name>/<version>/`. The publish
  workflow fetches pinned versions from their source repos at build time; the
  test suite fetches them into `.schema-cache/` and applies them to examples
  that declare them.

### Changed

- No `portolan:`-prefixed fields are defined: the versioned schema URI in
  `stac_extensions` is the single signal of specification version, declared
  on catalogs and collections only (items inherit conformance).
