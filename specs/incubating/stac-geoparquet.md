# Incubating — STAC-GeoParquet Beyond Raster Items

**Status: Maturing convention; may become required. Schema proposal drafted in
August 2026, to be taken upstream.**

The **item mirror** for raster collections is now ratified. See [Raster § Item
mirror](../portolan/formats.md#raster).

An item mirror is a STAC-GeoParquet file containing a collection's items. It is
**not** the provenance meaning of *mirror* used elsewhere in Portolan, where a
mirror is a catalog republishing data it did not produce. See [Source
Provenance](../portolan/core.md#source-provenance).

Raster item mirrors graduated first because existing `stac-geoparquet` tooling
already reads and writes `items.parquet`, and because raster scene collections
benefit most from avoiding large numbers of per-item JSON requests.

This document proposes the two remaining tiers: a GeoParquet file of a catalog's
collections, and a GeoParquet file of its catalogs. Together with per-collection
item mirrors they let a client search and reconstruct a whole catalog without a
STAC API. The proposal is meant for
[radiantearth/stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17).
Portolan tracks it in
[#44](https://github.com/portolan-sdi/portolan-spec/issues/44) and adopts the
upstream convention once one exists.

## Why Items Are Not Enough

The upstream [STAC GeoParquet
specification](https://github.com/radiantearth/stac-geoparquet-spec) (v1.1.0)
defines one row per STAC Item. Collections appear only in the Parquet file
metadata, as a map from collection ID to Collection JSON. That map is not a
table. A client cannot filter collections by area, time, or attribute without
parsing footer JSON.

For raster catalogs this is a scaling gap: a catalog with hundreds of
collections needs hundreds of `collection.json` fetches before it can open a
single item mirror.

For vector catalogs the gap is total. A [single-file
collection](../portolan/core.md#single-file-collections) exposes its GeoParquet
as a collection-level asset and has no items. Most vector layers in an SDI
catalog take this shape. No item mirror exists for them, so nothing in the
current convention lets a client search them without an API. A collections file
at the catalog root is the only API-free search surface for vector data.

## Principle

The proposal applies the item spec's approach one level up.

- One row per STAC object.
- STAC core fields become typed columns.
- `extent` explodes into `geometry`, `bbox`, `start_datetime`, and
  `end_datetime` so a query engine can prune row groups.
- Fields whose shape varies per publisher (`assets`, `summaries`, extension
  fields) are JSON text.
- Items are referenced, never contained. Each collection row carries the href
  of its data or of its item mirror.
- The catalog tree is an adjacency list. A collection row names its containing
  catalog in a `catalog` column, following the item spec's `collection` column.

## Files

| File | Rows | Status |
|------|------|--------|
| `collections.parquet` | one per Collection in the catalog tree | proposed, primary deliverable |
| `catalogs.parquet` | one per Catalog, root included | proposed, optional companion |
| `items.parquet` | one per Item, per collection | specified upstream; normative in Portolan for raster |

`collections.parquet` and `catalogs.parquet` sit at the catalog root next to
`catalog.json`. Both MUST be valid GeoParquet 1.1 with `geometry` in OGC:CRS84
and a `bbox` covering column. The [GeoParquet
requirements](../portolan/formats.md#vector) that apply to item mirrors apply
here too: rows spatially ordered, per-row-group spatial statistics, at most
150,000 rows per row group.

Catalog and Collection rows MUST NOT share one file. Their required columns
differ, so a mixed file forces every column to be nullable and every query to
filter on type first.

## Collections File

One row per Collection, including collections under nested sub-catalogs.

| Column | Arrow type | Required | Source and notes |
|--------|-----------|----------|------------------|
| `id` | string | Required | `id`. Unique within the catalog tree. Join key to the `collection` column of item mirrors. |
| `href` | string | Required | URL of the `collection.json`, absolute or relative to the Parquet file. |
| `catalog` | string, nullable | Optional; required when the file spans more than one catalog | `id` of the Catalog that directly contains this collection. Mirrors the item spec's `collection` column. |
| `title` | string | Optional | `title` |
| `description` | string | Required | `description` |
| `keywords` | `list<string>` | Optional | `keywords` |
| `license` | string | Required | `license` |
| `stac_extensions` | `list<string>` | Required, may be empty | `stac_extensions` |
| `geometry` | binary (WKB) | Required | Polygon of `extent.spatial.bbox[0]`. MAY be a MultiPolygon of `bbox[1..n]` when sub-extents exist. |
| `bbox` | struct of floats | Required | GeoParquet 1.1 bounding box column, 4 values. |
| `start_datetime` | timestamp (UTC), nullable | Required column | `extent.temporal.interval[0][0]`. Null when open. |
| `end_datetime` | timestamp (UTC), nullable | Required column | `extent.temporal.interval[0][1]`. Null when open. |
| `extent` | JSON text | Optional | Raw `extent` object, for lossless round-trip of extra intervals and sub-bboxes. |
| `providers` | `list<struct<name, description, roles, url>>` | Optional | `providers`. Fixed shape in STAC, so a struct is safe. |
| `summaries` | JSON text | Optional | `summaries`. No standard shape. |
| `links` | list of Link structs | Required | Same Link Struct as the upstream item spec. |
| `assets` | JSON text | Optional | `assets`. Asset keys are publisher-chosen, so a struct would widen the schema with every collection. |
| `item_assets` | JSON text | Optional | `item_assets` |
| `data_href` | string, nullable | Required column | href of the asset with role `data`. Set for single-file collections. |
| `data_type` | string, nullable | Optional | Media type of the `data` asset. |
| `item_mirror_href` | string, nullable | Required column | href of the asset with role `collection-mirror`. Set for collections that publish an item mirror. |
| `table_columns` | `list<struct<name, type, description>>` | Optional | `table:columns` from the STAC table extension. Fixed shape. |
| `properties` | JSON text | Optional | Every field not mapped above, including extension fields such as `portolan:*`. Name open; `extra_fields` avoids confusion with Item properties. |
| *extra columns* | varies | – | Publishers MAY add columns. Readers MUST ignore columns they do not know. |

`type` and `stac_version` are optional and not recommended, as in the item spec.

Every collection has at least one entry point. A single-file collection sets
`data_href`. A collection with items sets `item_mirror_href`. A collection MAY
set both.

`table_columns` is the vector-specific addition. It lets a client find every
layer with a given attribute without opening a data file. Portolan already
recommends `table:columns` for [tabular
collections](../portolan/formats.md#tabular-non-geospatial).

For a single-file GeoParquet collection, `extent.spatial.bbox` is the exact
bounds of the data, so the bbox polygon is not an approximation. Only raster
scene collections would gain from a footprint tighter than the bbox.

## Catalogs File

One row per Catalog, root included. Optional; flat catalogs need only
`collections.parquet`.

| Column | Arrow type | Required | Source and notes |
|--------|-----------|----------|------------------|
| `id` | string | Required | `id` |
| `href` | string | Required | URL of the `catalog.json`. |
| `parent_id` | string, nullable | Required column | `id` of the parent Catalog. Null for the root. |
| `title` | string | Optional | `title` |
| `description` | string | Required | `description` |
| `stac_extensions` | `list<string>` | Required, may be empty | `stac_extensions` |
| `links` | list of Link structs | Required | Same Link Struct as the upstream item spec. |
| `geometry` | binary (WKB) | Required | Derived: envelope of the `geometry` of every descendant collection. |
| `bbox` | struct of floats | Required | Derived, same rule. |
| `start_datetime` | timestamp (UTC), nullable | Required column | Derived: minimum over descendant collections. Null if any descendant is open. |
| `end_datetime` | timestamp (UTC), nullable | Required column | Derived: maximum over descendant collections. Null if any descendant is open. |
| `collection_count` | int64 | Optional | Number of descendant collections. |
| `properties` | JSON text | Optional | Every field not mapped above. |

A STAC Catalog has no `extent`. The writer computes the spatial and temporal
columns from descendant collections and MUST document that rule. A catalog with
no descendant collections has an empty geometry and null timestamps.

## Hierarchy

The `catalog` column in `collections.parquet` and the `parent_id` column in
`catalogs.parquet` form an adjacency list. A client walks a deep tree with a
recursive query. A materialized `path` column such as `root/hydrology/gauges`
is out of scope for the first version.

## Multi-Catalog Files

A `collections.parquet` MAY contain collections from more than one catalog.
This is the same generalization the item spec made for items from more than
one collection, one level up. A registry that aggregates many catalogs is the
main case: the registry is a catalog whose children are the registered roots,
so its `collections.parquet` is an ordinary collections file for a very wide
catalog.

The schema does not change. Collection rows always share the same typed
columns, so the columnar widening that makes the item spec discourage mixing
heterogeneous collections does not occur here. Three rules apply instead:

- `href` is the key. STAC collection `id`s are unique only within one catalog,
  so in a multi-catalog file `id` is not unique and `href` identifies a row.
  The `catalog` column is required, and `catalog` plus `id` disambiguates,
  the same way `collection` plus `id` disambiguates in a multi-collection
  item file.
- Hrefs MUST be absolute. With rows from several hosts there is no common
  base to resolve relative hrefs against. Absolute hrefs also preserve
  provenance: each row points to the authoritative `collection.json` in its
  home catalog.
- The file sits at, and is registered on, the lowest common ancestor: the
  topmost catalog that contains every row. For a registry that is the
  registry root, and the metadata `catalog` field holds that root's JSON. A
  row's `catalog` column still names its direct parent, not the root.

The item spec stopped short of this last rule: it defines registration only
per collection (`collection-mirror` on one `collection.json`), so a
multi-collection item file has no specified registration point. Anchoring the
file to the common root closes that gap at the collection level.

## Parquet Metadata

Both files store metadata under the existing `stac-geoparquet` key:

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | The stac-geoparquet version the file implements. |
| `catalog` | STAC Catalog object | The root Catalog JSON. |

This is symmetric with the item mirror, which embeds its Collection JSON under
`collections`.

## Registration

The root `catalog.json` registers each file as an asset with media type
`application/vnd.apache.parquet`:

| File | Role |
|------|------|
| `collections.parquet` | `catalog-mirror` |
| `catalogs.parquet` | `catalog-tree-mirror` (name open) |

The role names the container being mirrored, consistent with upstream's
`collection-mirror`, which names a mirror of one collection's items.

## Query Shape

Filter collections in one range request, then open only the matching data.

```sql
-- 1. Find collections by area, time, and attribute.
SELECT id, data_href, item_mirror_href
FROM read_parquet('https://example.org/catalog/collections.parquet')
WHERE ST_Intersects(geometry, ST_GeomFromText('POLYGON((...))'))
  AND end_datetime >= '2024-01-01'
  AND catalog = 'hydrology'
  AND list_contains(list_transform(table_columns, c -> c.name), 'population');

-- 2a. Single-file collections: open the data directly.
SELECT * FROM read_parquet('https://example.org/catalog/rivers/rivers.parquet')
WHERE ST_Intersects(geometry, ST_GeomFromText('POLYGON((...))'));

-- 2b. Item collections: open only the matching item mirrors.
SELECT * FROM read_parquet(
  ['https://example.org/catalog/a/items.parquet',
   'https://example.org/catalog/b/items.parquet'],
  union_by_name = true)
WHERE datetime BETWEEN '2024-01-01' AND '2024-12-31'
  AND ST_Intersects(geometry, ST_GeomFromText('POLYGON((...))'));
```

## Open Decisions

1. An optional `footprint` column derived from items, for collections that
   publish an item mirror.
2. `assets` as JSON text or as `Map<string, Asset struct>`. Follow whatever
   upstream decides for items in
   [stac-geoparquet-spec#7](https://github.com/radiantearth/stac-geoparquet-spec/issues/7).
3. Names of the catch-all column and of the catalogs-file role.
4. Whether `catalogs.parquet` ships with the first version or as a follow-on.

## Relation to Upstream

[stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17)
proposes a `collections` table with `id`, `extents`, and a JSON `properties`
catch-all, with extra columns allowed. This proposal keeps that catch-all and
adds the columns a search filters or joins on: a real `geometry`, typed temporal
bounds, `catalog`, `data_href`, `item_mirror_href`, and `table_columns`.

Full catalog reconstruction is no longer a separate long-term tier.
`catalogs.parquet`, `collections.parquet`, and per-collection `items.parquet`
together reconstruct catalogs, collections, items, and links.

This work belongs upstream in `stac-geoparquet`. Portolan adopts the upstream
convention once it exists rather than defining its own.
