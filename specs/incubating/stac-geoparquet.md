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

## STAC-GeoParquet Mirrors of Collections

An item mirror indexes the items in a single collection. A complementary
construct could index the collections in an entire catalog, regardless of
whether they contain COGs, vector data, or point clouds. Like `items.parquet`
within a collection, such a file would let clients search every collection in a
catalog with a single read. It would also provide the same capability for
collection types that do not currently publish item mirrors.

The encoding is still unsettled. Collection extents are ranges rather than
footprints, summaries have no standard representation, and no existing tooling
reads such a file.

## Complete STAC Catalogs in GeoParquet

The longer-term goal is a STAC-GeoParquet representation that can reconstruct an
entire catalog: catalogs, collections, items, and links stored in a queryable
set of Parquet files.

That work belongs upstream in `stac-geoparquet`. Portolan should adopt the
upstream convention once it exists rather than defining its own.
