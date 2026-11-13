# Incubating: STAC-GeoParquet catalog index

**Status: experimental, in use, and can change with upstream.**

A **catalog index** is one GeoParquet file with one row for each catalog and
each collection in one catalog tree. It contains the whole catalog except the
items. A client filters collections by place, time, and keywords with one
query, and fetches no `collection.json`.

Item mirrors contain the items. Raster item mirrors are normative. See [Raster
§ Item mirror](../portolan/formats.md#raster). Do not call the catalog index a
collection mirror. The upstream `collection-mirror` role names the item mirror.
A provenance mirror, a catalog that republishes data it did not produce, is a
different concept. See [Source
Provenance](../portolan/core.md#source-provenance).

## Status

The catalog index is experimental. The layout below follows the shape agreed
on 2026-11-04 in
[stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17).
Upstream has not released it, and the columns can change. When upstream
changes the schema, this document changes with it. Portolan does not define
its own variant.

A catalog MAY publish a catalog index now. When the layout changes, the
publisher rebuilds the file. A client SHOULD read the catalog JSON when the
file is missing or its columns do not match this layout.

## Link from the catalog

The catalog at the top of the indexed tree links to the file:

```json
{
  "rel": "data",
  "href": "./collections.parquet",
  "type": "application/vnd.apache.parquet",
  "title": "Catalogs and collections as GeoParquet"
}
```

The link MUST have `rel: "data"` and `type: "application/vnd.apache.parquet"`.
A client MUST match both values. Other `data` links, such as the one on a STAC
API landing page, point to JSON.

A catalog SHOULD publish the file as `collections.parquet` in its root
directory. Clients find the file by its link, not by its name.

## Columns

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

A file MUST include each MUST column. The values follow these rules:

- A `Collection` row MUST fill every column that copies a required field of a
  STAC Collection.
- A `Catalog` row fills only the fields of a STAC Catalog. Its `keywords` is
  null, because STAC defines `keywords` for collections only.
- `href` is absolute, or relative to the index file.
- `links` copies the `href`, `rel`, `type`, and `title` of each link, as the
  document writes them. Resolve a relative link `href` against the row's
  `href`.
- When a file has `parents`, every row fills it. The root catalog row has an
  empty list. An ancestor `href` matches the `href` of a `Catalog` row in the
  file, or points to a document outside the file.
- When `bbox[0]` crosses the antimeridian, `west` is greater than `east`. Split
  the geometry into a multipolygon at the antimeridian.

The links are the source of truth for the tree. `parents` is a copy of them
for one-predicate subtree filters. Filter ancestors by `href`, not by `id`.
STAC does not require unique catalog ids, so an `id` can match more than one
catalog.

The index MUST match the catalog and collection JSON at publication time. The
JSON stays the normative representation.

The file MUST be valid GeoParquet with the `bbox` column declared as its
covering. Rows SHOULD be spatially ordered. The file SHOULD use one row group.
Collections that cover a whole region or the world occur in each row group,
so smaller row groups let no query skip a row group. The search columns are
small, so a client reads each of them in one request.

## Example queries

These DuckDB queries need the spatial extension. The first returns the
collections under `transport` that intersect an area and have data from 2020
or later:

```sql
INSTALL spatial;
LOAD spatial;

SELECT id, title, href
FROM read_parquet('https://example.org/catalog/collections.parquet')
WHERE type = 'Collection'
  AND ST_Intersects(geometry, ST_MakeEnvelope(-3.9, 40.3, -3.5, 40.6))
  AND (end_datetime IS NULL OR end_datetime >= TIMESTAMP '2020-01-01')
  AND list_contains(list_transform(parents, lambda p: p.href),
                    'https://example.org/catalog/transport/catalog.json');
```

The second returns the sub-catalogs under `transport`. Catalog rows have no
geometry or time, so this query has no spatial or temporal filter:

```sql
SELECT id, title, href
FROM read_parquet('https://example.org/catalog/collections.parquet')
WHERE type = 'Catalog'
  AND list_contains(list_transform(parents, lambda p: p.href),
                    'https://example.org/catalog/transport/catalog.json');
```

The ancestor URL in the filter must match the `href` as the file stores it.
