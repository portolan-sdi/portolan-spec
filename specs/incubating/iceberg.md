# Incubating — Apache Iceberg Tables Over Published GeoParquet

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

The read side is what a static catalog gains. A manifest names every file, so a
client reads a partitioned collection over plain HTTPS without listing the
bucket. Per-file bounds let an engine skip a file without opening its footer. One
`ATTACH` exposes the catalog as a SQL namespace.

## Principles

Six rules follow from that position. The rest of this document applies them.

- **P1. STAC is the catalog, Iceberg is an access path.** The GeoParquet file
  keeps the `data` role. The Iceberg metadata file is a separate asset with the
  role `metadata`.
- **P2. One copy of the bytes.** The manifests reference the published GeoParquet
  by URI. The writer adds no data file and rewrites nothing.
- **P3. Static only.** The table lives under the collection directory and is read
  from its `metadata.json`. The convention requires no catalog server.
- **P4. Format version 3.** Version 3 is the first Iceberg format version with a
  native geometry type that carries a CRS.
- **P5. GeoParquet 2.0 is the data file.** The Iceberg Parquet mapping expects the
  `GEOMETRY` logical type, which a 2.0 file carries.
- **P6. The table is verified before it is published.** A reader opens it and
  returns the row count the GeoParquet file has.

## Where the table lives

The table lives under the collection directory:

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

The manifests hold the URI of each published GeoParquet file. Those URIs are
absolute, because an Iceberg reader resolves a data-file path against nothing.
A writer that stages the table before upload rewrites them to the public base.

## STAC representation

The collection declares the STAC Iceberg extension and carries one asset.

| Field | Value |
|---|---|
| `iceberg:catalog_type` | `static` |
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

Iceberg forbids inline PROJJSON in a type string. When the CRS has no authority
code, put the PROJJSON in a table property and name it as
`geometry(projjson:<property>)`.

The `table:columns` entry for the same column reports `geometry`, the logical
type, with no parameter. The two strings are different things. Do not copy one
into the other.

## Partitioned collections

A partitioned collection maps to an Iceberg partition spec of `identity` over
each entry in `partition:keys`:

- One Iceberg data file per partition file. The manifest and `partition:glob`
  list the same files, which a checker can compare.
- The partition cell column MUST stay in the data files. A writer reads the
  partition value from the column statistics, not from the directory name.
- Every partition file has the identical schema. That is already required by
  PORTO-FMT-021.

Iceberg has no spatial partition transform. The transforms are `identity`,
`bucket`, `truncate`, `year`, `month`, `day`, `hour`, and `void`, and `identity`
is excluded for a geometry column. So `identity` over a precomputed cell column
is the only mapping, and it is what a Hive-partitioned Portolan collection
already holds.

Hilbert ordering is an Iceberg sort order, not a partition. Row groups need no
alignment, because Iceberg prunes whole files. Row-group skipping stays with the
GeoParquet statistics and the bbox covering column, under PORTO-FMT-007 and
PORTO-FMT-009.

## Per-file bounds

A writer SHOULD write per-file geometry bounds, in the native CRS, computed from
the data. Bounds are what lets an engine skip a file.

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

## Verification

Open the table and compare it with the GeoParquet file:

```
duckdb -c "SELECT count(*) FROM iceberg_scan('<collection>/iceberg/metadata/v1.metadata.json')"
duckdb -c "DESCRIBE SELECT geom FROM iceberg_scan('<collection>/iceberg/metadata/v1.metadata.json')"
```

The count MUST equal the GeoParquet row count. The geometry column MUST come back
as a native `GEOMETRY`, not as `BLOB`. A writer that cannot show both deletes its
output.

## Open areas

**The static REST surface.** A catalog MAY serve a pre-rendered Iceberg REST
catalog under `v1/` at its public base, so a client attaches the whole catalog
with one call and no server. The namespaces mirror the catalog tree and each
table document points at the current `metadata.json`. Two questions stay open.
The first is whether the root `catalog.json` carries a link to `v1/config`, which
needs a link relation the extension does not define. The second is whether
discovery instead relies on `iceberg:catalog_uri` on each collection.

**Items tables.** A collection that publishes an item mirror can register that
mirror as an Iceberg table, which makes a raster scene collection searchable with
SQL. See [STAC-GeoParquet](stac-geoparquet.md). A single catalog-wide `items`
table is the more useful object and the harder one. Its column set freezes on
first publication, so it waits for its own decision.

## Engine support

Format version 3 geometry is young. As of September 2026, DuckDB reads the
Iceberg `geometry` type and answers "Geography support: not implemented" for
`geography`. PyIceberg reads version 3 metadata, but parses only a quoted CRS
parameter, so it cannot load a table a DuckDB or Java writer produced. Spark and
Trino have no metadata-file entry point and need a catalog server.

Treat `iceberg:format_version: 3` as a statement about the table, not a promise
that a given engine reads it.
