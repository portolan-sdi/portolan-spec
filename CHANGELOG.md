# Changelog

All notable changes to the Portolan specification are recorded here. The Portolan
STAC profile keeps its own changelog in [`stac/CHANGELOG.md`](stac/CHANGELOG.md).

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
under the pre-1.0 bump policy described in the [README](README.md#versioning).

## 0.1.2 - 2026-08-20

A catalog declares this version by carrying
`https://schemas.portolan-sdi.org/portolan/v0.1.2/schema.json` in `stac_extensions`.
The `v0.1.0` and `v0.1.1` schemas stay published unchanged, so a catalog authored
against either version keeps validating against it.

Nothing in this release asks more of a catalog that already conforms. The
fan-out guidance is a SHOULD that rashid reports as a warning, and the
multilingual rules permit a structure the profile previously left unspecified.
The schema carries no change beyond its own `$id`.

### Added

- `PORTO-CORE-078`: a catalog or collection with twenty or more children SHOULD
  organize them into subcatalogs, thematic or otherwise. A flat list of dozens
  of children is hard to browse, and the profile already allows a catalog at
  every level above a leaf, including below a collection. rashid reports the
  fan-out as a warning (`PTL-CAT-001`).
- **Multilingual catalogs** (`PORTO-CORE-079`, `PORTO-CORE-080`): catalogs can
  publish a separate STAC tree for each language. `alternate` links connect the
  trees without adding them to the catalog hierarchy. Each tree has its own root,
  while equivalent objects use the same IDs.
- **Multilingual catalog guidance**: a new best-practices page explains how to
  structure, link, translate, and maintain the language trees.
- **Requirements manifest**: 128 requirements, now 89 MUST, 22 SHOULD, and
  17 MAY.

### Changed

- **A `self` link is no longer forbidden** (`PORTO-CORE-034`,
  [`specs/portolan/core.md`](specs/portolan/core.md)): the rule now says only
  that structural links MUST be relative. Portolan takes no position on `self`.
  STAC treats the presence of one as the difference between a self-contained
  catalog and a [relative published
  catalog](https://github.com/radiantearth/stac-spec/blob/master/best-practices.md#relative-published-catalog),
  and both are legitimate: the first is portable, the second records where it is
  served from. Which one suits a catalog follows from how it is built and
  published, not from anything Portolan needs, so forbidding the link ruled out
  a layout STAC recommends for catalogs that live online without buying
  conformance anything (#159). Relaxing a constraint is non-breaking.

### Added

- **Guidance on `self` links for git-backed catalogs**
  ([`specs/best-practices/git-backed-catalogs.md`](specs/best-practices/git-backed-catalogs.md)):
  a new "Keep links relative" section, replacing the normative rule with the
  reasoning behind it. A git-backed catalog is authored in one place and served
  from another, so a tracked `self` link is either wrong for two of the three
  and produces diff and merge noise. The section recommends keeping the tracked
  tree free of `self` links and letting the publish step write an absolute one
  onto the root catalog from the `public_base` it already holds.

## 0.1.1 - 2026-08-14

A catalog declares this version by carrying
`https://schemas.portolan-sdi.org/portolan/v0.1.1/schema.json` in `stac_extensions`.
The `v0.1.0` schema stays published unchanged, so a catalog authored against that
version keeps validating against it.

Two changes ask something new of a catalog that already conforms. A collection
with more than one style now MUST mark exactly one style asset with the `default`
role (`PORTO-CORE-070`, raised from SHOULD), and a root catalog that publishes an
`icon` link MUST give it a `type` (`PORTO-CORE-075`).

### Added

- `PORTO-FMT-046` and `PORTO-FMT-047`: a vector collection SHOULD document its
  columns with the STAC [table](https://github.com/stac-extensions/table)
  extension, carrying `table:columns` on the collection, and an item holding a
  GeoParquet data asset SHOULD carry the field in its `properties`. Those are
  the two placements the extension defines, and the collection is the only one
  a partitioned collection has, since its data sits behind `partition:glob`
  rather than in an asset. `PORTO-FMT-048` permits per-asset declaration where
  a collection's data assets describe differing schemas. The same SHOULD
  already covered tabular collections (`PORTO-FMT-037`); nothing asked a vector
  collection for its schema, so a catalog could publish a hundred attribute
  columns that a client could only discover by reading the Parquet footer.
  The reference catalog moves `table:columns`, `table:primary_geometry`, and
  `table:row_count` from the `data` asset to the collection to match, and
  `examples/tools/stacio.py` writes them there from now on.
- **GeoParquet** (PORTO-FMT-044): a validator MUST NOT fail a file for missing a
  spatial-ordering threshold that its row-group count puts out of reach. Row
  ordering is a separate rule and is not waived along with those thresholds, so
  a file with fewer than five row groups is still checked on its rows (#127).
- **Data Storage** (PORTO-CORE-073): a validator MUST probe the servers hosting
  the catalog's own cloud-native assets and MUST NOT require upstream servers to
  satisfy the section's requirements. This writes down the carve-out reis
  already applies to upstream assets (#89).
- **Assets**: the `source` and `collection-mirror` roles are defined where the
  other roles are listed. `source` names the upstream original a cloud-native
  asset was derived from, which PORTO-FMT-002 has asked a mirror to carry since
  0.1.0; the role gives that asset a name and settles what carrying one costs.
  It is a reference, satisfied by an href pointing at the upstream server, so no
  publisher retains or rehosts an original to comply. `collection-mirror` is
  already required on a published item mirror by PORTO-FMT-041; this documents
  it rather than adding a requirement. Neither role is enumerated in the JSON
  Schema, which still accepts any non-empty role string (#90).
- **Formats** (PORTO-FMT-045): a validator MUST apply the format requirements to
  the catalog's own cloud-native assets and MUST NOT fail an asset for its
  format because that asset carries the `source` role. An upstream original is
  a Shapefile or a GeoPackage as often as not, and judging it as a COG or a
  GeoParquet was never intended. The role records provenance, not hosting;
  which servers the Data Storage requirements reach is settled by
  PORTO-CORE-073 (#90).
- **Catalog Logo** (PORTO-CORE-074 through PORTO-CORE-077): the root catalog MAY
  publish a logo as a link with `rel: "icon"`. A registry lists many catalogs
  side by side, and a logo makes each one recognizable before the reader has read
  a word. STAC defines no `logo` relation, `icon` is registered with IANA, and
  stac-js and STAC Browser already read it. An `icon` link MUST declare a `type`
  drawn from the seven image media types a browser renders in an `<img>` element,
  since a client drops an icon whose media type it does not recognize. The link
  SHOULD carry a `title`, which a page renders as the image's accessible label,
  and its `href` SHOULD be relative, which keeps the catalog portable. The
  reference catalog publishes the Portolan logo from `_assets/` (#136).
- **Git-backed catalogs**: a new best-practices page,
  [`specs/best-practices/git-backed-catalogs.md`](specs/best-practices/git-backed-catalogs.md),
  covers publishing a catalog whose source of truth is a Git repository. It
  recommends `vcs` and `issues` links on the root catalog so software can find
  the repository and its issue tracker. Both relations are registered with IANA.
  This is a recommended convention, not a Portolan requirement, and the page says
  so (#145).

### Changed

- Reworked the golden-example styles into named multi-variant sets, three to
  five per vector Collection (#81 follow-up, demonstrating the multiple
  data-driven styles `specs/best-practices/styling.md` recommends). Each
  manifest variant declares its own type, categorical, binned graduated,
  heatmap, outline, labels, or a raw-expression escape hatch, with a title and
  a description carried onto the asset. Graduated styles emit binned `step`
  expressions rather than continuous interpolates so clients can derive
  legends (#118). Collections that render from source, the two Natural Earth
  layers, now carry styles too, sourcing the GeoParquet itself, which
  portolan-browser binds onto the data it loads. `build.py --styles-only`
  re-authors styles against the committed tree without refetching data.
- **GeoParquet** (PORTO-FMT-006): the low-overlap and high-locality checks now
  apply only to files with five or more row groups, and the high-locality limit
  moves from about 25% of the file extent to about 30%. Both checks measure a
  percentage across the row groups, so with fewer than five groups the
  percentage cannot land on a useful value, and a well-ordered four-row-group
  file was failing for that reason alone. The 30% limit comes from measuring
  Hilbert-sorted data, which is how producers usually sort: boxes cover 0.263 to
  0.274 of the extent at five row groups and 0.250 to 0.270 at six, so the old
  25% failed those files for having few row groups rather than for their
  ordering. Files with seven or more groups already passed at 25%. The
  low-overlap limit is unchanged, as is the rule that rows MUST be spatially
  ordered, which still applies to every file. The 50% skip rate for a 10% query
  window now reads as the benefit the limit delivers, not as a second check
  (#127).
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
- **Requirements manifest**: 125 requirements, now 88 MUST, 21 SHOULD, and
  16 MAY.
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
