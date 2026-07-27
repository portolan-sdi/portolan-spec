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

Rows MUST be spatially ordered so nearby features are nearby in the file, tested
either as:

- **low overlap** — fewer than 30% of consecutive row-group pairs have
  interior-intersecting bounding boxes; or
- **high locality** — row-group boxes average under about 25% of the file extent,
  letting a reader skip at least 50% of row groups for a query window of 10% of the
  extent.

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
