# Incubating — STAC-GeoParquet Beyond Raster Items

**Status: Maturing convention; may become required.**

The **item mirror** for raster collections is now ratified. See [Raster § Item
mirror](../portolan/formats.md#raster).

An item mirror is a STAC-GeoParquet file containing a collection's items. It is
**not** the provenance meaning of *mirror* used elsewhere in Portolan, where a
mirror is a catalog republishing data it did not produce. See [Source
Provenance](../portolan/core.md#source-provenance).

Raster item mirrors graduated first because existing `stac-geoparquet` tooling
already reads and writes `items.parquet`, and because raster scene collections
benefit most from avoiding large numbers of per-item JSON requests.

Two extensions remain incubating.

## Collection index

A **collection index** is one GeoParquet file that describes a catalog tree. It
holds one row per catalog and one row per collection. An item mirror covers the
items of one collection. The collection index covers every collection in the
tree, whether it holds COGs, vector data, or point clouds. A client reads one
file and filters collections by place, time, and keywords with SQL. It needs no
STAC API server and fetches no `collection.json`. Tracked in
[#44](https://github.com/portolan-sdi/portolan-spec/issues/44).

Call it a collection index, never a collection mirror. The upstream
`collection-mirror` role names the item mirror, and reusing the word would make
the two constructs hard to tell apart.

The row schema belongs upstream, in
[stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17).
Version 1.1.0 of that specification stores whole collection objects in the
Parquet file metadata under the `collections` key. A query cannot filter on file
metadata, so that key does not replace a row per collection. Portolan adopts the
upstream schema when it is released and removes the provisional layout below.

### What Portolan needs from the upstream schema

Portolan argues for these properties in the upstream discussion:

- **One file for the whole tree.** A root catalog with thematic sub-catalogs
  publishes a single index. The file holds a row for each catalog and for each
  collection, and each row keeps its STAC links, so the file records the tree
  as it is. An aggregator is a catalog whose children are other catalogs, so a
  federated search uses the same file shape.
- **Spatial and temporal columns that existing tools filter on.** The overall
  spatial extent of a collection becomes the `geometry` column, so the
  GeoParquet requirements for spatial ordering and row-group statistics apply
  unchanged. A `bbox` struct column gives a GeoParquet 1.1 index its row-group
  statistics, as the items table does. GeoParquet 2.0 adds native statistics,
  and the column stays for readers that use the 1.1 path. The overall temporal
  interval reuses the item column names `start_datetime` and `end_datetime`.
- **Search fields at the top level.** `title`, `description`, `keywords`, and
  `license` are the fields people filter on, so each is its own column. STAC
  requires `description` on catalogs and collections, and `license` on
  collections, so the index can require them too.
- **A lossless row.** The row carries the full catalog or collection JSON, so a
  client can rebuild the document without a second request.
- **A pointer back.** The row carries the URL of its document, so a client can
  follow the catalog from a search result.
- **A subtree filter in one predicate.** An optional `parents` column lists the
  ancestors of each row. A filter on any ancestor then needs no tree walk in
  client code.

### Provisional layout

Until the upstream schema exists, a catalog MAY publish a collection index that
follows this layout. Expect the column names to change when upstream settles.

#### How a catalog links to the file

The catalog at the top of the indexed tree names the file with a link:

```json
{
  "rel": "data",
  "href": "./collections.parquet",
  "type": "application/vnd.apache.parquet",
  "title": "This catalog's catalogs and collections as GeoParquet"
}
```

The link MUST have `rel: "data"` and `type: "application/vnd.apache.parquet"`.
A client MUST check both values to find the file. A STAC API landing page also
has a `data` link, to the `/collections` endpoint, with the type
`application/json`. A client that follows the first `data` link without a check
of its type can read the wrong resource.

A STAC Catalog has no `assets` field. So the file is a link of the catalog, not
an asset as `items.parquet` is for a collection.

Clients find the file by its link, not by its name, so the upstream schema fixes
no file name. A Portolan catalog SHOULD publish the file as `collections.parquet`
in its root directory.

#### Columns

| Column | Type | Requirement | Catalog row | Collection row |
|--------|------|-------------|-------------|----------------|
| `type` | string | MUST | `Catalog` | `Collection` |
| `id` | string | MUST | The catalog `id` | The collection `id` |
| `href` | string | MUST | URL of the `catalog.json` | URL of the `collection.json` |
| `links` | list of struct of `href`, `rel`, `type`, `title` | MUST | The `links` of the document | The `links` of the document |
| `parents` | list of struct of `id`, `href` | MAY | The ancestors, from the root to the direct parent | The ancestors, from the root to the direct parent |
| `geometry` | GeoParquet 1.1 or 2.0 geometry, OGC:CRS84 | MUST | null | `extent.spatial.bbox[0]` as a polygon |
| `bbox` | struct of `xmin`, `ymin`, `xmax`, `ymax` | MUST | null | The 2D values of `extent.spatial.bbox[0]` |
| `start_datetime` | timestamp, UTC | MUST | null | `extent.temporal.interval[0][0]`, null when open |
| `end_datetime` | timestamp, UTC | MUST | null | `extent.temporal.interval[0][1]`, null when open |
| `description` | string | MUST | The catalog `description` | The collection `description` |
| `license` | string | MUST | null | The collection `license` |
| `original` | string, JSON | MUST | The full catalog document | The full collection document |
| `title` | string | SHOULD | The catalog `title`, null when absent | The collection `title`, null when absent |
| `keywords` | list of string | SHOULD | null | The collection `keywords`, null when absent |

A MUST column exists in every file. These rules apply to its values:

- A `Collection` row MUST fill every column that copies a field the STAC
  Collection specification requires. Every valid collection can fill them.
- A `Catalog` row fills the fields that a STAC Catalog has. It leaves
  `geometry`, `bbox`, `start_datetime`, `end_datetime`, `license`, and
  `keywords` null. STAC defines `keywords` for a Collection, not for a Catalog.
- STAC makes `title` and `keywords` optional, so the index can only recommend
  them.
- `href` is absolute or relative to the index. It identifies the row in any
  file, a federated index included.

`links` copies the `href`, `rel`, `type`, and `title` of each link in the
document, as the document writes them. Resolve a relative link `href` against
the row's `href`. The links are the source of truth for the tree.

`parents` is a copy of what the links already state. When a file has the
column, every row fills it, and the root catalog row holds an empty list. Each
element names one ancestor with its `id` and the URL of its document. The order
runs from the root to the direct parent. An ancestor `href` matches the `href`
of a `Catalog` row in the same file, or names a document outside the file.
Without `parents`, a client resolves each `parent` link and climbs the tree in
its own code.

STAC requires unique collection ids within one root catalog. It sets no such
rule for catalog ids. So a filter on an ancestor `id` can match more than one
catalog, and a filter on an ancestor `href` matches exactly one. In generic
STAC an ancestor can be a catalog or a collection. In Portolan every ancestor
is a catalog, because a collection never contains a child collection. See
[Nested Catalogs, Flat Collections](../portolan/core.md#nested-catalogs-flat-collections).

A collection whose bbox crosses the antimeridian has
`bbox[0]` with `west` greater than `east`. Split its geometry into a
multipolygon at the antimeridian.

The collection index is a derived copy. The catalog and collection JSON stay the
normative representation, and the index MUST match them at publication time,
exactly as an item mirror must match its items. Rows MUST follow the
GeoParquet requirements for vector datasets in
[formats.md](../portolan/formats.md).

A client can then search a catalog with one query:

```sql
SELECT id, title, href
FROM read_parquet('https://example.org/catalog/collections.parquet')
WHERE type = 'Collection'
  AND ST_Intersects(geometry, ST_MakeEnvelope(-3.9, 40.3, -3.5, 40.6))
  AND (end_datetime IS NULL OR end_datetime >= TIMESTAMP '2020-01-01')
  AND list_contains(list_transform(parents, lambda p: p.href),
                    'https://example.org/catalog/transport/catalog.json');
```

Remove the `type` filter, and the same query also returns the sub-catalogs
under `transport`. The [collection index
testbed](https://github.com/cayetanobv/stac-geoparquet-as-catalog-testbed)
measures this layout against Berlin, Comunidad de Madrid, and the Portolan
registry. Since 2026-11-05 the CARTO catalogs publish it, for example
`https://storage.googleapis.com/carto-open-catalogs/berlin-geoportal/main/collections.parquet`.

### Open questions

- **Variant or JSON text.** Upstream suggests the Parquet Variant type for the
  fields that differ between rows. DuckDB 2.0 reads Variant. The support in
  other engines decides whether Variant can replace `original`.
- **Summaries.** Collection summaries have no standard columnar form and stay
  inside `original` for now.
- **Memory.** A browser client holds the decoded file in memory. In the
  testbed, the registry index is 8.7 MB on disk and 85 MB as an Arrow table.
  `original` and `links` take 73 MB of that.
- **Item links.** `links` copies the `item` links of a collection. The registry
  index holds 151,188 of them. The spec does not yet say whether the index can
  leave them out.
- **Row groups.** The testbed result for row-group size changes between DuckDB
  1.5.6 and 2.0. No spatial filter skipped a row group, because each row group
  holds some global datasets. The layout states no row-group rule yet.
- **Table kind.** A file opened without its STAC context cannot tell a
  collection index from an item mirror. The `stac-geoparquet` file metadata can
  declare the kind of table.
- **Relation to the items schema.** The upstream schema must explain why the
  collection index differs from the items table. It must also say how the
  index relates to the `collections` key in the file metadata.
- **URL fragments.** An `href` such as `collections.parquet#transport` could
  name a row in the same file. The Parquet media type defines no fragment
  syntax, and ids can repeat in a federated file. Upstream defers this.
- **Registry.** The Portolan registry prototypes a collection index across
  registered catalogs in
  [portolan-registry#39](https://github.com/portolan-sdi/portolan-registry/issues/39).

## Complete STAC Catalogs in GeoParquet

The longer-term goal is a STAC-GeoParquet representation that can reconstruct an
entire catalog: catalogs, collections, items, and links stored in a queryable
set of Parquet files.

The collection index holds the catalogs and collections of such a catalog, and
item mirrors hold its items. The convention that joins them belongs upstream in
`stac-geoparquet`. Portolan should adopt the upstream convention once it exists
rather than defining its own.
