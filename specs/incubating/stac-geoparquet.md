# Incubating — STAC-GeoParquet Beyond Raster Items

**Status: maturing convention, may become required.**

The item rollup for raster collections is ratified. See [Raster § Item
rollup](../portolan/formats.md#raster). It graduated first because
[stac-geoparquet](https://github.com/stac-utils/stac-geoparquet) tooling already
writes and reads `items.parquet`, and because scene collections are where
per-item JSON fetches hurt most.

Three extensions of the idea are still open.

## Rollups for other collection types

Vector and point-cloud collections can carry an `items.parquet` on the same
terms. Portolan does not ask for one yet. A partitioned vector collection often
has no items at all, since `partition:glob` is the access path, and point cloud
support is itself unimplemented.

## A catalog-wide collections.parquet

A rollup of every collection in a catalog would let a client search across
collections in one read, as `items.parquet` does within one collection. The
encoding is unsettled. Collection extents are ranges rather than footprints,
summaries vary in shape, and no tooling reads such a file today.

## A whole STAC catalog in Parquet

Beyond either rollup, the longer-term goal is a Parquet representation complete
enough to reconstruct a catalog: catalogs, collections, items, and links in one
queryable set of files. That work belongs upstream in `stac-geoparquet` first.
Portolan should adopt the convention once it exists there, rather than invent a
parallel one.
