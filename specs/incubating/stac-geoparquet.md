# Incubating — STAC-GeoParquet Beyond Raster Items

**Status: maturing convention, may become required.**

The item mirror for raster collections is ratified. See [Raster § Item
mirror](../portolan/formats.md#raster). It graduated first because
[stac-geoparquet](https://github.com/stac-utils/stac-geoparquet) tooling already
writes and reads `items.parquet`, and because scene collections are where
per-item JSON fetches hurt most.

Both senses of *mirror* on this page are STAC-GeoParquet mirrors: Parquet copies
of STAC metadata. Neither is the provenance mirror of [Source
Provenance](../portolan/core.md#source-provenance), where a mirror is a catalog
republishing data it did not produce.

Two extensions of the idea are still open.

## A STAC-GeoParquet mirror of collections themselves

One construct should cover every collection a catalog holds, whatever the data
underneath — COGs, vector, point clouds. A Parquet mirror of the collections
would let a client search across a catalog in one read, as `items.parquet` does
within one collection, and would carry the same terms to collection types that
today publish no item mirror at all.

The encoding is unsettled. Collection extents are ranges rather than footprints,
summaries vary in shape, and no tooling reads such a file today.

## A whole STAC catalog in Parquet

Beyond an item mirror or a collection mirror, the longer-term goal is a Parquet
representation complete enough to reconstruct a catalog: catalogs, collections,
items, and links in one queryable set of files. That work belongs upstream in
`stac-geoparquet` first. Portolan should adopt the convention once it exists
there, rather than invent a parallel one.
