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

Rows MUST be spatially ordered so nearby features are nearby in the file.[^rowrule]
Order is judged by pruning efficiency, defined next, on the row groups where the
footer check below applies and on the rows otherwise.

**Pruning efficiency.** The input is a set of `n` bounding boxes
`B_i = (bx0, by0, bx1, by1)`. The extent `E = (X0, Y0, X1, Y1)` is the union of
those boxes, not the bbox the file declares. A query window is `w = 0.10 (X1 − X0)`
wide and `h = 0.10 (Y1 − Y0)` tall, and its lower-left corner is uniformly
distributed on `[X0, X1 − w] × [Y0, Y1 − h]`. The window hits box `B_i` with
probability

```
Px = max(0, min(bx1, X1 − w) − max(bx0 − w, X0)) / (X1 − X0 − w)
Py = max(0, min(by1, Y1 − h) − max(by0 − h, Y0)) / (Y1 − Y0 − h)
P  = Px · Py
```

A factor whose denominator is zero or less is 1: the extent has no width on that
axis, so every window hits every box there. The expected skip rate of a layout is
the share of its boxes a window misses:[^expectation]

```
skip = 1 − mean(P_i)
```

The reference layout is a full tiling of the extent into `n` cells, so it covers the
whole extent with no empty cells. With `cols = ceil(sqrt(n))` and
`rows = ceil(n / cols)`, every row is `(Y1 − Y0) / rows` tall; every row but the
last holds `cols` cells, each `(X1 − X0) / cols` wide; the last row holds the
remaining `n − cols · (rows − 1)` cells, each `(X1 − X0) / (n − cols · (rows − 1))`
wide, so it too spans the full width. Efficiency is the ratio of the two skip rates,
clipped at 1:

```
efficiency = min(1, skip(layout) / skip(reference))
```

A layout passes when its efficiency is 0.70 or more. When the reference skip rate is
0, which takes an extent with no area, the efficiency is undefined and the layout is
not judged.

Efficiency measures order relative to the extent, not relative to where the data
lies. When a few far features stretch the extent so that most of it is empty, every
box is small against it, and a shuffled file can pass. When features are large
against the extent, no order makes their boxes small, and a sorted file can fail.
Both are properties of the data, not of the sort, and the area sum
`Σ area(B_i) / area(E)` shows them: it is the same expectation with a window of
zero size, and a re-sort that leaves the verdict unchanged can still shrink it
several times over.

**Footer check.** A file with eight or more row groups MUST pass on its row-group
boxes, read from the per-row-group spatial statistics.[^pruning] Below that floor
the rule is not judged from the footer: a validator MUST NOT report a pass or a fail
from the row groups, and MAY report the numbers.[^floor] Wherever it reports
a verdict, a validator MUST also report the area sum, as a statistic and not as a
verdict.

**Row check.** Where the footer check is not judged, the rows are judged by the
abstract test recorded with `PORTO-FMT-006` in the [requirements
manifest](requirements.yaml): the same efficiency, applied to ten equal chunks of
the rows in file order. That test needs 200 rows. Below that a validator MUST
report that the file has too few rows to judge, and MUST NOT stay silent.

The fraction of consecutive row-group pairs whose boxes overlap MAY be reported as a
statistic, but MUST NOT decide the verdict.[^overlap]

[^rowrule]: On a file with one row group, order does not change read performance,
    because a reader fetches the whole file either way. The row rule buys
    consistency across a catalog, and correct pruning on the day a publisher repacks
    the file into more row groups.

[^expectation]: The skip rate is an expectation, not a sample. Drawing query windows
    at random and counting the boxes each one misses converges to this number, and a
    rule written that way — twenty windows from a fixed seed — moved its verdict with
    the seed on real files. The closed form is that sample's limit, so no seed,
    window count, or draw order is part of the rule.

[^pruning]: Pruning is the benefit spatial ordering exists to deliver, and the footer
    boxes already carry what it takes to estimate it. The bar is relative because the
    achievable rate rises with the row-group count: two row groups can never skip
    more than half a file, five hundred about 98%. The bar is set from
    measurements over the Portolan registry and four further catalogs, recorded in
    the [changelog](../../CHANGELOG.md).

[^floor]: A grid is a poor model of a curve sort at small counts. Well-sorted files
    from several catalogs score 0.60 to 0.88 at five row groups and 0.76 to 0.94 at
    eight, so the verdict starts at eight.

[^overlap]: A space-filling-curve sort makes neighboring row groups adjacent, so
    their boxes touch and this fraction runs near 1.0 even for a perfectly tiled
    file.

Files MUST provide per-row-group spatial statistics so readers can skip row groups
from metadata alone — either:

- a GeoParquet 1.1 `bbox` covering column with Parquet min/max statistics on its
  leaf fields (a `bbox` column without statistics does not qualify); or
- for GeoParquet 2.x / Parquet `GEOMETRY`, native `GeospatialStatistics` per
  geometry column chunk.

For 2.x, a covering column remains RECOMMENDED even where native statistics exist,
since it adds page-level min/max stats that enable finer-grained pruning.

Row groups MUST hold no more than 150,000 rows.

A vector collection SHOULD document its columns with the STAC
[table](https://github.com/stac-extensions/table) extension, carrying
`table:columns` with names, types, and descriptions on the collection itself.
An item that carries a GeoParquet data asset, as when partition files are
modeled as items, SHOULD carry the same field in its `properties`. Those are
the two places the extension scopes the field to, and the collection is the
only one available to a partitioned collection, whose data sits behind
`partition:glob` rather than in an asset. A collection whose data assets
describe differing schemas MAY declare `table:columns` per asset instead.

Without it the attribute names and types live only in the Parquet footer, so a
client has to read the file to learn what the collection holds. Names and types
can be generated from the Parquet schema. The descriptions are written once and
belong in both the metadata and the README schema table.

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
