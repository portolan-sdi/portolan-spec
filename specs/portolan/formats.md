# Portolan Specification — Formats

This document defines the format-specific requirements. The format-agnostic
requirements are in [`core.md`](core.md).

STAC allows assets in any format, but Portolan requires that every collection and
item is available in a cloud-optimized format, and adds requirements on specific
ones: in general GeoParquet and PMTiles for vector, COG for raster, COPC for point
clouds, and Parquet for non-spatial data. A mirror SHOULD also include the original
data as an asset when it is directly downloadable (not just an API). Catalogs
SHOULD reference alternate formats of data and metadata — for example an existing
ISO 19115 file referenced as an asset with the `metadata` role — though new
catalogs need not pre-produce them, since tooling should make translation easy.

The requirements in this document apply to the catalog's own cloud-native assets: copies that the publisher derives and publishes. They do not apply to `source` assets, which represent the upstream originals from which those copies were derived and may use a non-cloud-native format.

A validator MUST apply the format requirements in this document to the catalog's own cloud-native assets and MUST NOT fail an asset for its format because it carries the `source` role. The `source` role identifies provenance, not hosting. The Data Storage requirements in core.md apply according to who hosts the bytes, as specified there, regardless of the roles an asset carries.

## Vector

Vector has no single complete cloud-native format yet, so Portolan pairs two strong
ones — GeoParquet and PMTiles — in a single STAC entity; the community is upgrading
GeoParquet toward a more complete answer while watching formats like Iceberg, and
this pairing will likely relax once GeoParquet gains overviews and more browsers
render it directly.

### GeoParquet

Data MUST be provided in GeoParquet 1.1 or 2.0, following the [Best Practices for
Distributing GeoParquet](https://guide.cloudnativegeo.org/geoparquet/) so it can be
queried without a server. Files SHOULD be compressed to stay small, with `zstd`
RECOMMENDED.

Rows MUST be spatially ordered so nearby features are nearby in the file. This rule
applies to every file, no matter how many row groups it has. A validator checks it
by looking at the rows themselves. It splits them into the groups a conforming
writer would have produced, then checks that each of those groups covers a small
part of the file.

A file with five or more row groups gets a second check, using the row groups it
actually has. A reader can run this one from the file footer alone, without reading
any data. The file passes if either of these is true:

- **low overlap** — fewer than 30% of consecutive row-group pairs have bounding
  boxes that overlap on their interiors; or
- **high locality** — row-group bounding boxes cover, on average, less than about
  30% of the file's total extent.

Boxes that small let a reader skip about half the row groups when querying a window
covering 10% of the extent. That is the benefit the 30% figure is meant to deliver,
not a separate test to run.

The 30% figure comes from measuring Hilbert-sorted data, which is how producers
usually sort. With five row groups, Hilbert-sorted boxes cover about 27% of the
extent, and that number drops as row groups are added. Five row groups divide the
extent five ways, so each box covers about a fifth of it before any overlap is
counted. A stricter limit would fail well-sorted files for having few row groups.

Neither of these two checks applies to a file with fewer than five row groups. Both
measure a percentage across the row groups, and with only a few groups the
percentage cannot land on a useful value. Three row groups can only produce an
overlap of 0%, 50%, or 100%. Two or three boxes cannot average less than 30% of the
extent, however well the rows are sorted. A validator MUST NOT fail a file for
missing a threshold that its row-group count puts out of reach. Row ordering is a
separate rule and is not waived here, so a file with fewer than five row groups is
still checked on its rows.

Files MUST provide per-row-group spatial statistics so readers can skip row groups
from metadata alone — either:

- a GeoParquet 1.1 `bbox` covering column with Parquet min/max statistics on its
  leaf fields (a `bbox` column without statistics does not qualify); or
- for GeoParquet 2.x / Parquet `GEOMETRY`, native `GeospatialStatistics` per
  geometry column chunk.

For 2.x, a covering column remains RECOMMENDED even where native statistics exist,
since it adds page-level min/max stats that enable finer-grained pruning.

Row groups MUST hold no more than 150,000 rows.

### PMTiles

A PMTiles file SHOULD be provided as the visualization derivative,
web-map-optimized and range-request friendly. It MUST be registered through a
collection-level `rel: "pmtiles"` link per the
[web-map-links](https://github.com/stac-extensions/web-map-links) extension
(v1.3.0): type `application/vnd.pmtiles`, a `pmtiles:layers` array of
default-visible layers, with the extension's v1.3.0 schema declared in
`stac_extensions`. The `pmtiles:layers` array MUST be non-empty; an empty list
leaves a client with nothing to display. Because PMTiles exists for
visualization and partial reads
rather than download, it is expressed as a link by default; when a provider intends
the PMTiles file as a genuine distribution format of the data, it MAY additionally
be registered as a collection-level asset, and the link and the asset then coexist.

When PMTiles are provided, the collection MUST include at least one visualization
style as a standalone STAC asset with the `["style"]` role, registered per
[Visualization Styles](core.md#visualization-styles). For PMTiles the style is a
MapLibre GL style file (MapLibre GL style spec v8) in a `styles/` subdirectory, with
media type `application/vnd.mapbox.style+json`, a complete, self-contained JSON
loadable directly by MapLibre GL JS. By convention such a file sets `version` 8, a
human-readable `name`, `sources.data.url` as the relative path from `styles/` to the
PMTiles file (typically `../filename.pmtiles`), and `layers[].source` to `"data"`.

### Partitioned Collections

Large files MAY be partitioned. Partitioning MUST be described per the
[partition extension](https://github.com/portolan-sdi/stac-partition-extension)
(v1.0.0), with its schema declared in `stac_extensions` and its required fields
carried — `partition:scheme`, `partition:keys`, and `partition:glob`. Field
definitions live in the extension and are not restated here. Portolan adds the
requirements the extension does not cover:

- The scheme's path structure MUST reflect spatial extent so readers can prune
  files without reading metadata.
- `partition:glob` is the normative bulk-access path; the collection description
  SHOULD also mention the glob for human readers, but validators read only the
  field. The https-only rule for absolute asset hrefs does not extend to the
  glob: globs are consumed by partition-aware readers rather than browsers, and
  bucket-native schemes (`s3://`, `gs://`) MAY be used where those readers need
  them (glob expansion requires listing, which plain https does not provide).
- Every partition file MUST share a single Parquet schema — the same columns,
  names, and types — so the glob can be queried as one table. This is validated
  by tooling reading file footers, not by JSON schema.

Partition files MAY be represented as items when partitions are user-meaningful
units (countries, regions); for opaque schemes (hilbert, s2, h3) or hundreds of
partitions, items SHOULD NOT be created — the glob pattern is the access path.

As a rough guide, consider partitioning files over ~2 GB, targeting 200 MB–1 GB per
file — fewer, larger files outperform many small ones for DuckDB. This is not
prescriptive; tune to your data and access patterns.

## Raster

Raster data MUST be provided as Cloud Optimized GeoTIFF (COG) for efficient
range-request access without full download. A COG here means a valid COG per the
[OGC Cloud Optimized GeoTIFF standard](https://docs.ogc.org/is/21-026/21-026.html)
(OGC 21-026): an internally tiled GeoTIFF carrying georeferencing keys, with a
header ordered so a reader can find the data it needs in an early range request.
This is the baseline that
[`rio cogeo validate`](https://cogeotiff.github.io/rio-cogeo/CLI/#validate) and
rasterio treat as a COG.
(Formats such as GeoZarr are candidates for future support once default tooling can
render and consume them.)
How a raster collection is structured — one item per scene, with a single-COG
collection handled as a single-file collection — is defined under [Raster
Collections](core.md#raster-collections).

**Optimized GeoTIFF conformance.** Beyond that baseline, a COG MUST conform to OGC
21-026's [Optimized GeoTIFF requirements
class](https://docs.ogc.org/is/21-026/21-026.html#optimized_geotiff-requirements-class)
(`/req/optimized_geotiff`), which adds three requirements:

- [Small tiles](https://docs.ogc.org/is/21-026/21-026.html#_requirement_small_tiles)
  (`/req/optimized_geotiff/small-sizes`): square internal tiles, sized no larger than
  a common screen viewport. 512×512 is the usual choice.
- [Reduced-resolution subfiles
  number](https://docs.ogc.org/is/21-026/21-026.html#_requirement_reduced_resolution_subfiles_number)
  (`/req/optimized_geotiff/number`): internal overviews, each reducing resolution by a
  factor between 2 and 10, extending until the coarsest level spans one tile across or
  down.
- [GeoTIFF
  keys](https://docs.ogc.org/is/21-026/21-026.html#_requirement_geotiff_2)
  (`/req/optimized_geotiff/geotiff`): georeferencing on the full-resolution IFD.

The overview requirement is the one that bites in practice. A raster larger than a
single internal tile needs internal overviews so a reader can display it zoomed out
without fetching full-resolution pixels; one that already fits within a tile is exempt,
since it is its own overview. Base COG validators, including `rio cogeo validate`,
treat missing overviews as a warning rather than a failure. Portolan raises this to a
requirement.

**Raster statistics.** COGs MUST carry pixel statistics for rendering. Every band
MUST carry an embedded minimum, maximum, mean, and standard deviation so a renderer
can scale any data type without reading pixels. Statistics MUST be embedded in the
file — an external `.aux.xml` (PAM) sidecar does not satisfy this — and MUST be
written at creation time (e.g. `gdal_translate -of COG -stats`), residing in the
file's leading header block so they arrive in a reader's first range request.

The required statistics are:

| Statistic | Requirement |
|-----------|-------------|
| Minimum, maximum, mean, standard deviation | **MUST** |
| Valid percent | SHOULD (MUST when the band has a nodata value) |
| Approximate flag (`STATISTICS_APPROXIMATE = YES`) | MUST when estimated |

The exact on-disk encoding (the TIFF `GDAL_METADATA` tag and its XML layout, and
`GDAL_NODATA`) is specified in
[`specs/incubating/geotiff-stats-headers.md`](../incubating/geotiff-stats-headers.md).
Compliance is defined by the tag contents, not by use of GDAL.

**Item mirror.** A raster collection that models scenes as items SHOULD also publish a
[stac-geoparquet](https://github.com/stac-utils/stac-geoparquet) item mirror at
`items.parquet` in the collection root. One range request then returns the whole
collection's item metadata, in place of one HTTP fetch per scene. Clients can search a large
scene collection, or assemble it into a data cube, without a STAC API server.

An **item mirror** is a Parquet copy of a collection's items. This is distinct from
Portolan's provenance meaning of *mirror*, where a mirror is a catalog republishing data it
did not produce. See [Source Provenance](core.md#source-provenance).

Always refer to this construct as an **item mirror** or **STAC-GeoParquet mirror**, never
simply **mirror**.

No item-count threshold applies. Tooling generates the item mirror directly from the item
JSON, and avoiding repeated JSON fetches provides a benefit even for small collections.

A published item mirror MUST be registered as a collection-level asset carrying media type
`application/vnd.apache.parquet` and the role `collection-mirror`, per [Referencing STAC
Geoparquet Collections in STAC Collection
JSON](https://radiantearth.github.io/stac-geoparquet-spec/latest/#referencing-a-stac-geoparquet-collections-in-a-stac-collection-json).
That single registration is the whole requirement; no `rel: "items"` link is needed.

The item JSON remains the normative representation. An item mirror is a derived Parquet copy
and MUST exactly reproduce the collection's items at publication time: one row per item,
with every row containing that item's fields.

An item mirror that falls out of sync with its source items produces incorrect query
results, and clients have no reliable way to detect the mismatch.

The GeoParquet requirements above apply to item mirrors exactly as they apply to vector
datasets. Rows MUST be spatially ordered, the file MUST include per-row-group spatial
statistics, and row groups MUST contain no more than 150,000 rows. Clients query an item
mirror spatially just as they query any other GeoParquet dataset.

A collection containing only a single COG has no items and therefore publishes no item
mirror. Item mirrors for other collection types, and STAC-GeoParquet mirrors covering an
entire catalog's collections, remain incubating. See
[`specs/incubating/stac-geoparquet.md`](../incubating/stac-geoparquet.md).

Raster styling (colormaps, legends, continuous vs. categorical vs. multiband) is
still under discussion — see
[`specs/incubating/raster-styling.md`](../incubating/raster-styling.md).

## Tabular (Non-Geospatial)

Portolan supports non-geospatial tabular data as companion data to a catalog's
spatial layers — tables keyed by time, administrative code, or category rather than
by location (e.g. census demographics by tract ID, permit records by parcel number,
budget allocations by administrative unit, or time-series such as sensor readings).
Tabular support is scoped to data that relates to the same geographic area as the
catalog's spatial layers; Portolan is not a general-purpose data catalog.

A tabular collection MUST be distinguishable from a geospatial one so that
validators and federation agents relax spatial requirements and route queries
correctly. No explicit marker property is defined; a tabular collection is
identified by its data, a Parquet asset with no geometry column. This MAY be
revisited in a future version if implicit detection proves insufficient.

Data MUST be provided as a Parquet file (`application/vnd.apache.parquet`) exposed
as a collection-level asset with role `["data"]`, following the single-file
collection pattern — no item directory or item JSON. Where a source file is
converted (e.g. a CSV), the original MAY be retained as an alternate asset under
the [primary-vs-alternate](core.md#assets) rule, with the Parquet as the primary.

Spatial requirements are relaxed. STAC requires `extent.spatial.bbox` on every
collection, so a tabular collection MUST still carry one, but it represents the
area of interest the data pertains to, not a geometry footprint, and validators
MUST treat it as informational. GeoParquet spatial metadata, PMTiles and other
visualization derivatives, and geometry validation do not apply, as there is no
geometry.

Tabular collections SHOULD populate `extent.temporal` when the data has a time
dimension, and SHOULD document their columns with the STAC
[table](https://github.com/stac-extensions/table) extension (`table:columns` with
names, types, and descriptions). Because tabular data has no geometry to signal its
meaning, the column schema is the primary semantic handle for consumers and agents.

When geometry and attributes live in separate files (e.g. census geometries joined
to a demographics table), the metadata MUST document the join columns explicitly in
the README and MUST include a working code example showing how to join them. Richer
multi-file relationship modeling (via the table extension or [Apache
Ossie](https://ossie.apache.org/)) is still being worked out.

All other Portolan core requirements apply unchanged: `collection.json`,
`README.md`, `AGENTS.md`, providers, and `via` provenance links.

```
eurostat-electricity-prices/
├── collection.json
├── AGENTS.md
├── README.md
├── electricity-prices.parquet
└── electricity-prices.csv   (source, if converted)
```

## Point Cloud

Point cloud support is not yet implemented; when complete, data MUST be provided as
Cloud-Optimized Point Cloud (COPC). Full requirements will follow a reference
implementation — see [`specs/incubating/point-cloud.md`](../incubating/point-cloud.md).
