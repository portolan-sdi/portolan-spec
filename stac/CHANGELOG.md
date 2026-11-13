# Changelog

All notable changes to the Portolan STAC profile will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- The extension registry lists the [Classification](https://github.com/stac-extensions/classification)
  extension at `v2.0.0`, SHOULD for classified rasters, with
  `classification:classes` on the asset for a single-band raster and on the
  band for a multiband raster (#41).
- A [classified raster example](examples/raster-classified-collection.json),
  the GEP SAR Features flood classification over Valencia, October 2024.
- `check-portolan` applies the Portolan class rules to classes on an asset
  and in STAC 1.1 `bands`. It also checks classes in `bands` against the
  classification schema, because the `v2.0.0` schema checks the asset and
  `raster:bands` only.
- The schema checks the new rules that STAC JSON alone can show:
  - A data asset `href` contains no `*` and no `[`, so an IPv6 literal
    host fails too (`PORTO-FMT-065`, #237).
  - A PMTiles asset has the `visual` role (`PORTO-FMT-062`, #230). The
    schema reads the `.pmtiles` extension from the `href` path only, not
    from the query or the fragment.
  - Every item has an asset with the `data` role (`PORTO-CORE-083`, #203).
  - A single-band raster has its `classification:classes` on the asset, and
    a multiband raster has them on the band in `bands`. Every class has a
    `title` (`PORTO-FMT-050`, `PORTO-FMT-052`, #222). A class list in the
    legacy `raster:bands` fails. The rules apply to `assets` and
    `item_assets`.
  - These format rules skip an asset with the `source` role
    (`PORTO-FMT-045`).
  - `partition:glob` is an absolute URL whose scheme is not `http` or
    `https` (`PORTO-FMT-064`, #230, #237).

### Changed

- The STAC profile uses Contacts v1.0.0 instead of v0.1.1 (#53).
- `json-schema/schema.json` is the one schema file. It is the draft of the next
  version. Each released version is published from its git tag, and every
  published schema keeps its bytes (#244).
- The schema accepts an absolute asset `href` with a scheme other than
  `https`, such as `s3://`, if the asset's `alternate` field has an `https`
  URL with a nonempty host (`PORTO-CORE-023`, `PORTO-CORE-087`, #240).
  Before, the schema rejected every absolute `href` that was not `https`.
  An `href` is absolute when it starts with a URI scheme and a colon, so
  `file:/data/x.parquet` and `C:/data/x.parquet` need the alternate too.
- The [partitioned collection example](examples/vector-partitioned-collection.json)
  has an `s3://` value for `partition:glob`, which the schema now requires
  (#245).

The schema does not check the other rules added since 0.2.0. They need the
items of a collection, the asset bytes, the server, or a comparison of two
fields: `PORTO-CORE-082`, `PORTO-CORE-085`, `PORTO-FMT-057`, the second
condition of `PORTO-FMT-062`, and the range and CORS rules. The SHOULD rules
stay with tooling, as `file:size` and `file:checksum` do.

## 0.2.0 - 2026-08-28

The schema is published at
<https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json>. The `v0.1.0`,
`v0.1.1`, and `v0.1.2` schemas stay published unchanged.

This is the first schema change since `v0.1.0`. `v0.1.1` and `v0.1.2` each
carried a new `$id` and nothing else.

### Changed

- The `links_conformant` block accepts a `self` link. The branch that mapped
  `rel: "self"` to `false` is gone, following the spec's retirement of
  `PORTO-CORE-034` (#159).
- The `links_conformant` block accepts an absolute structural `href`. The
  `"not": {"pattern": "://"}` constraint is gone from the
  `root`/`parent`/`child`/`collection` branch and from the `item` branch.
  `PORTO-CORE-034` carried that rule too.

The rest of the block is unchanged. Structural links still carry the required
media type, `child` and `item` links still carry a title, and an `icon` link
still declares a renderable media type.

The new recommendation of a root `self` link (`PORTO-CORE-081`) is conditional
on how the publisher serves the catalog, so the schema does not check it. A
validator resolves an absolute structural link through the base that the root
`self` link names, which the schema also cannot check.

## 0.1.2 - 2026-08-20

The schema is published at
<https://schemas.portolan-sdi.org/portolan/v0.1.2/schema.json>. The `v0.1.0` and
`v0.1.1` schemas stay published unchanged.

### Changed

- The schema is identical to `v0.1.1` apart from its `$id`. The specification
  release adds `PORTO-CORE-078`, `PORTO-CORE-079`, and `PORTO-CORE-080`, none of
  which the schema can check: the fan-out rule counts children across the tree,
  and the multilingual rules govern `alternate` links between separate roots.
  The version directory exists because the schema URI is the signal of
  specification version, and a released schema is immutable.

## 0.1.1 - 2026-08-14

The schema is published at
<https://schemas.portolan-sdi.org/portolan/v0.1.1/schema.json>. The `v0.1.0`
schema stays published unchanged.

### Changed

- The extension registry now records the table extension as SHOULD for vector
  collections as well as tabular ones, and names the two placements the
  extension defines, matching `PORTO-FMT-046` and `PORTO-FMT-047`. The vector
  examples carry `table:columns` on the collection, and the partitioned item
  carries it in `properties`. The schema is unchanged.
- The schema no longer requires `file:size` and `file:checksum` on every asset,
  following the specification's move of both to SHOULD. Where either is present
  the schema still checks its shape, and tooling still checks the checksum's
  multihash encoding and its agreement with the bytes. A catalog that conformed
  before still conforms, so this is a non-breaking relaxation under the pre-1.0
  bump policy.
- The extension registry lists File Info as a conditional MUST, owed when an
  asset carries either field rather than on every object with assets.
- `PORTO-CORE-026`: `image/webp` is now a valid thumbnail media type alongside
  `image/png` and `image/jpeg`. No existing catalog breaks.
- A link with `rel: "icon"` now MUST carry a `type`, and the schema restricts it
  to `image/apng`, `image/avif`, `image/gif`, `image/jpeg`, `image/png`,
  `image/svg+xml`, and `image/webp`, matching core.md's Catalog Logo section. The
  section's other two rules, a relative `href` and a `title`, are SHOULD-level,
  so Portolan tooling reports them and the schema does not. A catalog that
  carries an icon link without a media type conformed before and does not now.
- The media types and roles table lists the `source` and `collection-mirror`
  roles, which catalogs already carry. The schema is unchanged: `roles` stays a
  non-empty array of non-empty strings with no enumeration, so no previously
  accepted value is removed.

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
