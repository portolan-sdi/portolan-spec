# Incubating — Apache Iceberg tables over published GeoParquet

**Status: Open — convention only, nothing normative
([#200](https://github.com/portolan-sdi/portolan-spec/issues/200)).**

A Portolan catalog MAY publish an [Apache Iceberg](https://iceberg.apache.org/)
table over data it already publishes. This document records how, so that two
implementations produce the same thing. Nothing here is part of the conformance
surface, and the validator applies no rule from it.

## Position

STAC is the catalog. It says what the data is, who published it, and how to draw
it. An Iceberg table is a second access path to the same bytes, for engines that
read Iceberg. It says how to query the data.

The read side is what a static catalog gains. A manifest lists every file, so a
client reads a partitioned collection over plain HTTPS without listing the
bucket. Per-file bounds let an engine skip a file without opening its footer. One
`ATTACH` exposes the catalog as a SQL namespace.

The convention describes the artifact a reader opens, not the system that wrote
it. A publisher may keep the table in a managed Iceberg catalog, and many do, for
concurrent writes and snapshot maintenance. That stays on the publisher's side.
What Portolan requires is that the reader reaches the same table from the
metadata file alone.

## Principles

These rules follow from that position. The rest of this document applies them.

- **P1. STAC is the catalog, Iceberg is an access path.** The GeoParquet file
  keeps the `data` role. The Iceberg metadata file is a separate asset with the
  role `metadata`.
- **P2. One copy of the bytes.** The live data files of the declared snapshot
  are exactly the collection's data assets. Each file appears once, under one
  name, and both trees end at the same bytes.
- **P3. A reader needs no server.** The collection declares
  `iceberg:metadata_location`, and that file resolves with the same access the
  collection's data assets need. A reader opens the table from it with no
  catalog service. Where the table is stored, and whether a catalog server also
  manages it, is the publisher's choice.
- **P4. Format version 3.** Version 3 is the first Iceberg format version with a
  native geometry type that carries a CRS.
- **P5. GeoParquet 2.0 is the data file.** The Iceberg Parquet mapping expects the
  `GEOMETRY` logical type, which a 2.0 file carries.
- **P6. The table is verified before it is published.** A reader opens it and
  returns the row count the GeoParquet file has.

## Two directions, one copy

P2 holds whichever side writes first. The direction decides who creates the
files, not what the reader finds.

**STAC-first.** The catalog publishes GeoParquet, then a writer registers those
files as a table. PyIceberg `add_files` does this and copies nothing. The Portolan
CLI takes this direction.

**Iceberg-first.** Where an engine writes the table first, the collection's
`data` asset points at the file that table stores. A managed catalog usually
produces a collection of this form.

Either way the check is the same. Compare the live data files of the declared
snapshot with the collection's data assets, and find no difference.

## Table location

A catalog written STAC-first SHOULD store the table under the collection
directory:

```
<collection>/
  collection.json
  boston-open-space.parquet
  iceberg/
    metadata/
      v1.metadata.json
      version-hint.text
      snap-<id>-1-<uuid>.avro
      <uuid>-m0.avro
```

Links inside the collection are relative, as everywhere else in Portolan. The
publishing step uploads `<collection>/iceberg/` with the rest of the collection.

A table an engine manages lives wherever that catalog puts it, which is often a
warehouse prefix outside the catalog tree. The layout is then the catalog's, and
`iceberg:metadata_location` is what ties it back to the collection.

The manifests record the URI of each published GeoParquet file. Those URIs are
absolute, because an Iceberg reader resolves a data-file path against nothing.
A writer that stages the table before upload rewrites them to the public base.

## STAC representation

The collection declares the STAC Iceberg extension and carries one asset.

| Field | Value |
|---|---|
| `iceberg:catalog_type` | `static`, or the catalog that manages the table |
| `iceberg:metadata_location` | path to the current `metadata.json` |
| `iceberg:format_version` | `3` |
| `iceberg:table_id` | `<namespace>.<collection id>` |
| `iceberg:current_snapshot_id` | the snapshot id, as a string |
| `iceberg:partition_spec` | present when the collection is partitioned |

The asset is keyed `iceberg`, carries the role `metadata` alone, and uses the
media type `application/vnd.apache.iceberg+json`. It never replaces the `data`
asset, and the `data` asset never changes because a table exists.

```json
{
  "iceberg:catalog_type": "static",
  "iceberg:table_id": "portolan.boston_open_space",
  "iceberg:metadata_location": "./iceberg/metadata/v1.metadata.json",
  "iceberg:format_version": 3,
  "iceberg:current_snapshot_id": "4358210771845678999",
  "assets": {
    "data": {
      "href": "./boston-open-space.parquet",
      "type": "application/vnd.apache.parquet",
      "roles": ["data"]
    },
    "iceberg": {
      "href": "./iceberg/metadata/v1.metadata.json",
      "type": "application/vnd.apache.iceberg+json",
      "roles": ["metadata"]
    }
  }
}
```

The snapshot id is a string. Iceberg snapshot ids are 64-bit, and a JSON parser
that stores numbers as doubles rounds them above 2^53.

## Type mapping

The Iceberg column type comes from the GeoParquet `geo` metadata, not from the
Arrow schema an Arrow reader infers.

| GeoParquet | Iceberg type string |
|---|---|
| `crs` absent | `geometry(OGC:CRS84)` |
| `crs.id` gives authority `A` and code `C` | `geometry(A:C)` |
| `edges: spherical` | `geography(A:C, spherical)` |

Write the parameter unquoted, as `geometry(EPSG:4326)`. That is the form the
Iceberg specification, the Java implementation, and DuckDB use.

The Iceberg specification rejects inline PROJJSON in a type string. When the CRS
has no authority code, put the PROJJSON in a table property and name it as
`geometry(projjson:<property>)`.

The `table:columns` entry for the same column reports `geometry`, the logical
type, with no parameter. Keep each string in its own field.

## Partitioned collections

A partitioned collection maps to an Iceberg partition spec of `identity` over
each entry in `partition:keys`:

- One Iceberg data file per partition file. The manifest and `partition:glob`
  list the same files, which a checker can compare.
- The partition cell column MUST stay in the data files. A writer reads the
  partition value from the column statistics, not from the directory name.
- The partition files share one schema. PORTO-FMT-021 already requires that.

Iceberg has no spatial partition transform. The transforms are `identity`,
`bucket`, `truncate`, `year`, `month`, `day`, `hour`, and `void`, and `identity`
is excluded for a geometry column. So `identity` over a precomputed cell column
is the only mapping, and it is what a Hive-partitioned Portolan collection
already holds.

Hilbert ordering maps to an Iceberg sort order. Row groups need no
alignment, because Iceberg prunes whole files. Row-group skipping stays with the
GeoParquet statistics and the bbox covering column, under PORTO-FMT-007 and
PORTO-FMT-009.

## Per-file bounds

A writer SHOULD write per-file geometry bounds, in the native CRS, computed from
the data. Bounds are what lets an engine skip a file.

Whether an engine uses them depends on the predicate. DuckDB prunes on a bbox
predicate,
such as `ST_Intersects_Extent` or `&&`, and reads one file of ten on the test
fixtures. A plain `ST_Intersects` returns the same rows and reads every file,
because the optimizer derives no bbox from it.

A writer that registers existing files without reading them writes no bounds. The
collection extent does not substitute: it is a WGS84 bounding box for the whole
collection, and the bounds are per file in the file's own CRS.

## Field identifiers

Iceberg selects a column by field id. A Parquet file may carry `PARQUET:field_id`,
and a file without one is read through the table property
`schema.name-mapping.default`.

Field ids are not required here. The name mapping is the standard fallback and
works end to end today. A field id that disagrees with the table schema is worse
than no field id, because the reader then fails instead of falling back. So a
writer either assigns the ids together with the table schema, or writes none.

## The snapshot moves, so the collection follows

A table a catalog manages is mutable. Each commit writes a new metadata file and
a new snapshot, while the collection still points at the earlier pair. So the
collection goes stale the moment the table moves, and it says nothing about
having gone stale. The rules below close that window.

**Pinning.** The collection states the exact metadata file and the exact
snapshot it describes, never a moving pointer such as `version-hint.text`. After
a commit, regenerate in this order: the collection, then any catalog-level index
row, then the root link. A reader that arrives mid-regeneration then finds an
older complete view, never a newer broken one.

**Retention keeps what STAC names.** Snapshot expiry and orphan-file removal run
on the catalog's own schedule. Neither may delete a file that a published
collection still lists as a data asset. A retention window shorter than the
publishing cycle breaks P2 silently, because the STAC tree keeps pointing at
files the table has dropped.

## Verification

Open the table and compare it with the GeoParquet file:

```
duckdb -c "SELECT count(*) FROM iceberg_scan('<collection>/iceberg/metadata/v1.metadata.json')"
duckdb -c "DESCRIBE SELECT geom FROM iceberg_scan('<collection>/iceberg/metadata/v1.metadata.json')"
```

The count MUST equal the GeoParquet row count. The geometry column MUST come back
as a native `GEOMETRY`, not as `BLOB`. A writer that cannot show both deletes its
output.

A validator that reads `iceberg:metadata_location` can check P2 and P5 without
the writer. It plans the declared snapshot and compares its live data files with
the collection's data assets. It then reads each file's footer for the `geo`
key. A reader depends on both, and a maintenance job breaks both.

## Open areas

**The static REST surface.** A catalog MAY serve a pre-rendered Iceberg REST
catalog under `v1/` at its public base, so a client attaches the whole catalog
with one call and no server. The namespaces mirror the catalog tree and each
table document points at the current `metadata.json`. Discovery is undecided. The
root `catalog.json` could carry a link to `v1/config`, which needs a link
relation the extension does not define. A client could instead read
`iceberg:catalog_uri` from each collection.

**Items tables.** A collection that publishes an item mirror can register that
mirror as an Iceberg table, which makes a raster scene collection searchable with
SQL. See [STAC-GeoParquet](stac-geoparquet.md). One catalog-wide `items`
table is the more useful object and the harder one. Its column set freezes on
first publication, so it waits for its own decision.

**A collection index.** A catalog MAY publish one table holding a row per
collection, so a client finds a collection with SQL instead of walking the
catalog JSON. The root `catalog.json` names it with a `rel: "alternate"` link.

The row schema is not Portolan's to define.
[STAC-GeoParquet](stac-geoparquet.md) already records that a catalog-level
GeoParquet belongs upstream, and the shape is under discussion in
[stac-geoparquet-spec#17](https://github.com/radiantearth/stac-geoparquet-spec/issues/17).
This document describes the link only, and adopts the upstream schema when it
settles.

## Engine support

Format version 3 geometry is young. Measured on DuckDB 1.5.6, PyIceberg 0.12.0
and Apache Iceberg 1.12.0, in September 2026:

- **DuckDB** reads the `geometry` type and prunes on its bounds. It answers
  "Geography support: not implemented" for `geography`.
- **PyIceberg** opens a version 3 table and plans its files. It parses only a
  quoted CRS parameter, so it cannot load a table a DuckDB or Java writer
  produced, and it cannot write version 3 at all.
- **BigQuery** rejects the type at `CREATE EXTERNAL TABLE`.
- **Spark** gained geometry read and write in Iceberg 1.12.0. It and Trino still
  have no metadata-file entry point, so both need a catalog server.

`iceberg:format_version: 3` states what the table is. Check the engine
separately.
