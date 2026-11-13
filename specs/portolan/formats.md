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
GeoParquet toward a more complete answer, and this pairing will likely relax once
GeoParquet gains overviews and more browsers render it directly.

A collection can also publish an Apache Iceberg table over the same GeoParquet
files, which gives an Iceberg engine a second way to read them. That convention is
recorded in [Iceberg](../incubating/iceberg.md). It is optional and adds no
requirement to this document.

### Parquet

Publishers MUST provide data as [GeoParquet 1.1](https://geoparquet.org/releases/v1.1.0/),
[GeoParquet 2.0](https://geoparquet.org/releases/v2.0.0/), or Parquet with native
[`GEOMETRY` or `GEOGRAPHY`](https://github.com/apache/parquet-format/blob/master/Geospatial.md)
logical types.
Publishers SHOULD follow the [Best Practices for Distributing
GeoParquet](https://guide.cloudnativegeo.org/geoparquet/) so readers can query
the data without a server. Files SHOULD be compressed to stay small, with `zstd`
RECOMMENDED.

A file with a native geospatial column is vector data, even without a `geo`
metadata key. A validator MUST apply every requirement in this section to the
file. Apache Iceberg writers commonly produce these files, so catalogs can
publish an Iceberg table's data files directly.

When a geometry column declares its CRS only through the native logical type's
`crs` field, the value MUST use one of the four formats that the [Parquet
geospatial specification](https://github.com/apache/parquet-format/blob/master/Geospatial.md)
suggests. These formats are inline PROJJSON, `projjson:<key>`,
`<authority>:<code>`, and `srid:<identifier>`. An absent `crs` value means
OGC:CRS84, as that specification defines.
The value SHOULD be inline PROJJSON or a `projjson:<key>` reference. Readers
can resolve either from the file alone. Values in `<authority>:<code>` or
`srid:<identifier>` form require a CRS registry. A validator reports these
values as warnings.

Rows MUST follow a spatial order that places nearby features near each other in the file.[^rowrule]
A row group is a set of rows that Parquet stores together.
Its footer statistics let a reader skip the group without reading its data.
A bbox covering stores each row's bounding box in separate fields.

A validator judges spatial order with pruning efficiency on one of two paths.
A file with eight or more row groups takes the footer check.
The count includes only row groups with a bounding box.
A file with fewer than eight row groups takes the row check.
Both checks use the same metric and the same pass bar.[^paths]
A conformance validator gives a verdict on every file that has enough rows.
Other tools can report the statistics without a verdict.

**Pruning efficiency.** Pruning means that a reader skips data it does not
need for a query. The skip rate is the share of the file's bytes that the
reader can skip. Efficiency compares this rate with the rate for a reference
layout over the same extent.

The metric takes a layout of `n` bounding boxes
`B_i = (bx0, by0, bx1, by1)`. Each box has a row count `r_i` and a byte count
`s_i`. For a row group, the footer supplies its row count and total compressed
size. A layout without byte counts uses `s_i = r_i`.
The row check's chunks use this substitution.
The extent `E` is the union of the boxes. The metric does not use the bbox
that the file declares.

A query window represents the area that a reader queries.
The metric places this window where the data is and sizes it to the data's
scale.[^placement] It chooses box `B_i` with probability `r_i / N`, where
`N = Σ r_i`. It then places the window's center `c` uniformly within that box.
The window spans 10% of each dimension of `B_i`.
Its width is `w = 0.10 (bx1_i − bx0_i)` and its height is
`h = 0.10 (by1_i − by0_i)`.

To calculate whether the window overlaps `B_j`, expand `B_j` by half the
window's size on each side. The window overlaps `B_j` exactly when `c` falls
inside this expanded box. The following formula calculates that probability
without a random sample.[^expectation]
On one axis, `[a0, a1]` is the span of `B_i` from which the metric draws the
center coordinate. The expanded target span is
`[g0, g1] = [bx0_j − w/2, bx1_j + w/2]`.
The overlap probability on that axis is:

```
F = clip((min(a1, g1) − max(a0, g0)) / (a1 − a0), 0, 1)
```

A span with no width (`a1 = a0`) has only one possible center coordinate.
In that case, `F` is 1 when `g0 <= a0 <= g1` and 0 otherwise.
The probability that a query window overlaps `B_j` combines the factors for
both axes:

```
P_j = Σ_i (r_i / N) · Fx(i, j) · Fy(i, j)
```

The expected skip rate weights each box by its share of the file's bytes.
This measures the data transfer that a reader avoids:

```
skip = 1 − Σ_j (s_j / S) · P_j        where S = Σ s_j
```

The reference grid divides the extent into cells that serve as a comparison
layout. The reference layout MUST use the following near-square grid of `n`
cells with uniform `r_i` and `s_i`.[^grid]
The construction is:

```
cols = ceil(sqrt(n))
rows = ceil(n / cols)
last = n − cols · (rows − 1)
```

Every grid row is `(Y1 − Y0) / rows` tall.
Every row except the last has `cols` cells, each `(X1 − X0) / cols` wide.
The last row has `last` cells, each `(X1 − X0) / last` wide.
Each row spans the full width of the extent.
The grid covers the whole extent with no empty cells.
Efficiency is the layout's skip rate divided by the reference skip rate,
clipped at 1:

```
efficiency = min(1, skip(layout) / skip(reference))
```

A layout passes when its efficiency is 0.65 or more.
The validator gives no verdict when the reference skip rate is 0, because
efficiency is undefined. This occurs for `n = 1` and for an extent that is a
point. At a point, every span has no width and every `F` is 1.
The validator does judge an extent that is zero on only one axis.
The one-coordinate rule gives that axis a factor of 1.
The other axis determines the score.

A validator MUST reproduce the expected values in the abstract test vectors in
[`abstract-tests/spatial-metric-vectors.json`](abstract-tests/spatial-metric-vectors.json).
These vectors specify the results of the preceding definitions.

Efficiency measures order at the scale of the row groups.
The metric places windows by row count and sizes them to the box around
their center. A few distant features cannot stretch the extent to make a
shuffled file pass or a sorted file fail.
The vectors `outlier-shuffled-n20` and `outlier-sorted-n20` test these cases.
Large features can still make a sorted file fail.
No spatial order can make their bounding boxes small relative to the extent.
The area sum is the sum of the box areas divided by the extent's area,
`Σ area(B_i) / area(E)`. This statistic helps identify files with large
features. A sort can reduce the area sum several times over without changing
the verdict.

**Footer check.** A file with eight or more row groups MUST reach the pass
bar on its row-group boxes.[^pruning]
The validator reads these boxes from the per-row-group spatial statistics.
A validator MUST NOT judge a file with fewer than eight row groups by its
row-group boxes. It MAY report their statistics.[^floor]
When the efficiency of the row-group boxes is undefined, the validator applies
the row check.

**Row check.** For a file with fewer than eight row groups, or without
per-row-group spatial statistics, the validator applies the abstract test for
`PORTO-FMT-006` in the [requirements manifest](requirements.yaml). This test
computes the same efficiency on ten chunks of rows in file order. It weights
each chunk by its row count.
A row's box is its bbox covering when the file has one.
Otherwise, the box is the minimum and maximum of the row's coordinates in the
primary geometry column.
This rule lets the row check judge native files without a covering.
For `GEOGRAPHY`, the coordinate box is an approximation, because geodesic
edges can extend past their vertices.
A row with a null covering, or a null or empty geometry, has no box.
The test needs 200 rows with a bounding box. Below that count, a validator
MUST report that the file has too few rows to judge. It MUST NOT withhold that
message.

**Reporting.** A validator MUST start its verdict with the expected share of
the file's bytes that the query window reads.
This states the absolute cost, as in "a typical query reads 23% of the file".
Wherever it reports a verdict, a validator MUST also report the efficiency,
the achievable skip rate, and the area sum as statistics.
These statistics do not give separate verdicts.
The achievable skip rate is the reference grid's skip rate.
When the extent has no area, the area sum is undefined.
A validator MUST report an undefined area sum as absent rather than as 0.
On a failure, a validator SHOULD identify the row groups whose boxes are
largest relative to the extent.
This helps a publisher see whether one outlier or the whole file causes the
failure. A validator SHOULD also report the read share for windows at 1% and
at 25% of each dimension beside the 10% figure.

A validator MAY report the fraction of consecutive row-group pairs whose
boxes overlap as a statistic. It MUST NOT base its verdict on that fraction.[^overlap]

[^rowrule]: Spatial order does not change read performance for a file with one
    row group. A reader fetches the whole file in either case.
    The row rule keeps files consistent across a catalog.
    It also lets readers prune correctly after a publisher repacks the file
    into more row groups.

[^paths]: The verdict depends on the order of the rows. It does not depend
    on the file size or the compression codec. In the November 2026
    row-check calibration on 654 registry files, shuffled rows never reached
    0.65, and the highest scored 0.52. Hilbert-sorted rows had a median of
    0.90. On the same rows, the footer check at eight row groups and the row
    check agreed on 648 files. The
    [calibration README](abstract-tests/calibration/README.md) links the data.

[^placement]: An earlier draft placed the window uniformly over the extent
    and sized it to that extent. One distant row could stretch the
    extent enough to make a shuffled file pass.
    Most windows then fell on empty space.
    The same outlier could make a sorted file fail because the window grew
    as large as the whole data region.
    The current metric avoids both errors with information from the footer.
    It places windows by row count and sizes them to the box around their
    center.

[^expectation]: The skip rate is the expected value of a sampling process.
    Draw a row at random, draw a query window around it, and count the bytes
    that the window reads. The mean converges to this value.
    An earlier rule sampled twenty windows from a fixed seed.
    On real files, a different seed could change the verdict.
    The formula calculates the limit of that sample.
    It needs no seed, window count, or draw order.

[^grid]: Validators need the same reference grid to produce comparable
    efficiency scores. Different tilings still give different skip rates,
    although the box-scaled window reduces the difference from the
    extent-scaled window. At n = 8, strips skip 0.864 and the grid skips 0.858.
    The vectors `five-strips-n5` and `three-boxes-old-vs-new-reference` test
    the required grid.

[^pruning]: Spatial order lets readers prune data.
    The footer boxes provide enough information to estimate this benefit.
    The pass bar is relative because the achievable skip rate rises with the
    row-group count. With two row groups, a reader can never skip more than half a file.
    Five hundred can skip about 98%.
    The 0.65 bar comes from the
    [calibration corpus](abstract-tests/calibration/README.md).
    The survey used this metric in November 2026 on 5,914 files from 74
    registry catalogs. Hilbert-sorted copies of the tested low scorers with
    eight or more row groups scored 0.696 to 0.944.
    The one file that a sort improved from below 0.70 scored 0.668 before the
    sort and 0.912 after it.

[^floor]: A grid is a poor model of a curve sort at small row-group counts.
    Each half of a curve can span most of the extent.
    In the row-check calibration, Hilbert-sorted rows failed the footer check
    in 70% of files at two row groups, 13% at four, 2% at eight, and 0.2% at
    sixteen. The row check uses ten chunks, which behave like eight to ten
    row groups.

[^overlap]: A space-filling-curve sort places neighboring row groups next to
    each other in space. Their boxes share boundaries, so the overlap fraction can be
    near 1.0 even for a file whose boxes tile the extent.

[^pagestats]: A reader with page-level statistics can skip individual pages
    within row groups. The row-group read share overstates how much data
    that reader needs to fetch.
    A refined read share provides more information beside the verdict,
    as do the 1% and 25% windows.


Files MUST provide per-row-group spatial statistics so readers can skip row groups
from metadata alone — either:

- a GeoParquet 1.1 `bbox` covering column with Parquet min/max statistics on its
  leaf fields (a `bbox` column without statistics does not qualify); or
- for GeoParquet 2.x / Parquet `GEOMETRY` or `GEOGRAPHY`, native
  `GeospatialStatistics` per geometry column chunk.

For GeoParquet 2.x, a covering column remains RECOMMENDED even where native
statistics exist, since it adds page-level min/max stats that enable
finer-grained pruning. A file without a `geo` key cannot declare a covering
column, so native statistics alone meet the preceding requirement.

A validator MAY use page-level statistics to refine the read share it reports.
These statistics can come from the Parquet page index on the covering leaves
or from page-level native statistics.
The verdict uses the preceding row-group metric.
Validators agree on the verdict whether or not they read the page index.[^pagestats]

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

A PMTiles asset MUST meet both conditions:

- The asset has the `visual` role.
- The asset belongs to a collection that references the GeoParquet data used
  to create the PMTiles file.

Use an asset with the `data` role or `partition:glob` for the GeoParquet
reference. PMTiles alone is not sufficient as a collection's primary data.

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

- For a spatial scheme (`kdtree`, `h3`, `s2`, `quadkey`, or `a5`), file paths
  MUST indicate each file's geographic extent. Readers can then skip files
  without reading their metadata. Paths for `temporal` and `attribute`
  partitions do not need to indicate spatial extent.
- Use `partition:glob` for bulk access. The collection description SHOULD
  also include the glob for human readers. Validators read the field only.
- Bucket-native schemes (`s3://`, `gs://`) MAY be used when partition-aware
  readers need them. These readers need to list the files that match the glob.
- `partition:glob` MUST NOT use `http://` or `https://`. Plain HTTP does not
  support listing the files that match a glob.
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

**Raster statistics.** COGs MUST include pixel statistics for rendering.
For each band, the file MUST include an embedded minimum, maximum, mean, and
standard deviation. Renderers use these values to scale any data type without reading
pixels.

Publishers MUST embed these statistics in the COG file.
A separate `.aux.xml` (PAM) file does not meet this requirement.

Publishers MUST write the statistics at creation time, in the file's leading
header block. Readers then receive the statistics in the first range request.
One command for this is `gdal_translate -of COG -stats`.

Embedded statistics MUST describe the full-resolution pixels stored in each
band. Publishers may use estimates if they set `STATISTICS_APPROXIMATE = YES`.

The required statistics are:

| Statistic | Requirement |
|-----------|-------------|
| Minimum, maximum, mean, standard deviation | **MUST** |
| Valid percent | SHOULD (MUST when the band has a nodata value) |
| Approximate flag (`STATISTICS_APPROXIMATE = YES`) | MUST when estimated |

For a non-finite nodata value, use the corresponding string in the band's
`nodata` field: `"nan"`, `"inf"`, or `"-inf"`. These strings are specified in
[STAC 1.1.0 common metadata](https://github.com/radiantearth/stac-spec/blob/v1.1.0/commons/common-metadata.md#bands).
Do not use `null` or an unquoted `NaN` in this field.

A valid-percent statistic is required even when the nodata value is non-finite.

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

A tabular collection MUST include `extent.spatial.bbox`, as required by STAC.
Use the bounds of the geographic area the table is about.
The bounding box does not describe a geometry footprint.
Validators MUST treat the bounding box as informational.

Tabular data has no geometry. GeoParquet spatial metadata, visualization
derivatives such as PMTiles, and geometry validation are not required.

For a table of European electricity prices, use the bounds of Europe.
For a tabular collection in a country catalog, use that country's bounds.

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
