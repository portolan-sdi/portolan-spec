# Incubating — Zarr raster stores

**Status: Open — draft profile, awaiting implementations
([#132](https://github.com/portolan-sdi/portolan-spec/issues/132)).**

Portolan intends to support Zarr as a raster format beside COG, in
[`formats.md`](../portolan/formats.md). This profile stays in incubation until
more complete implementations exist. That means catalogs that follow every rule
here, and support for those rules in the validator, the CLI, and the browser.
Reports from those implementations can change any rule before the profile
graduates.

Nothing here is part of the conformance surface for the current Portolan
version. The requirements below carry `PORTO-ZARR` IDs in the
[requirements manifest](../portolan/requirements.yaml), marked
`status: incubating`, so that the validator can check a store against them.

## Scope

A Zarr store is a hierarchy of groups and arrays under one root URL. The
requirements in this document apply to the store that the asset `href` points
to, as a standard Zarr v3 reader reads it over HTTP. The storage system behind
that URL is not constrained. An Icechunk repository served as plain Zarr v3
can conform. Virtual stores are out of scope for this version of
the profile.

This document uses these terms:

- A **renderable array** is a data variable that has both spatial dimensions.
  Coordinate arrays are not renderable arrays.
- A **chunk** of a sharded array is an inner chunk. A **shard** is the outer
  chunk that holds inner chunks.
- The **spatial dimensions** are the two dimensions that `spatial:dimensions`
  names.

## Store

A store MUST be Zarr v3. It MUST declare these conventions in
`zarr_conventions` and conform to them:

- [spatial](https://github.com/zarr-conventions/spatial);
- [proj](https://github.com/zarr-conventions/proj); and
- [multiscales](https://github.com/zarr-conventions/multiscales), where
  [Overviews](#overviews) requires a pyramid.

## Access

- The store MUST be served over `https`, with an
  `Access-Control-Allow-Origin` header that permits cross-origin reads.
- The STAC asset MUST follow the
  [asset organization](https://github.com/radiantearth/stac-best-practices/blob/main/best-practices-zarr.md#asset-organization)
  rules of the STAC Zarr Best Practices, with media type
  `application/vnd.zarr; version=3`.
- An `s3://` href MAY be given beside the `https` one.

## Grid

- Every renderable array MUST have an affine
  [`spatial:transform`](https://github.com/zarr-conventions/spatial#spatialtransform).
  The transform is the authoritative grid.
- The spatial axes MUST be the last two dimensions of every renderable array,
  Y before X.
- Arrays MUST be stored row-major (C order).

## Coordinate reference system

These rules apply to the attributes of the Zarr store under the proj
convention. They do not apply to the STAC Projection extension fields of the
same names.

- The store SHOULD carry `proj:code`.
- A store without `proj:code` SHOULD carry `proj:projjson`.

## Overviews

- A store whose finest level needs more than 4 chunks to cover its full extent
  MUST provide a multiscale pyramid.
- The coarsest level MUST fit in 4 chunks or fewer.
- Each `layout` entry MUST carry `spatial:transform` and `spatial:shape`, per
  the spatial convention's
  [multiscales usage](https://github.com/zarr-conventions/spatial#usage-with-multiscales-convention).
- Levels SHOULD step by a factor of 2.
- An append to a pyramided store MUST target the level-0 group, not the store
  root.

## Variables

A store with more than one data variable MUST declare `cube:variables` per
the [datacube](https://github.com/stac-extensions/datacube#variable-object)
extension.

## Display range

Every renderable array MUST carry at least one of:

- a `statistics` object with `minimum` and `maximum`, on the entry of the
  asset's `bands` array whose `name` equals the variable name; or
- a `rescale` in a `renders` entry, per the
  [render](https://github.com/stac-extensions/render) extension.

A store that is 8-bit with three or more bands is exempt.

Band `statistics` and band `nodata` describe the stored values, per the STAC
[bands](https://github.com/radiantearth/stac-spec/blob/master/commons/common-metadata.md#bands)
definition. An authored display range or a display-only no-data value belongs
in `renders`.

## No data

A renderable array SHOULD declare `nodata` on its `bands` entry. A store with
partial coverage SHOULD carry an alpha band named `alpha` instead.

## Chunking

- A store MUST NOT require a client to read more than 8 samples for every
  sample it draws, for one timestep at full resolution. The factor is the
  product of the chunk lengths along the non-spatial dimensions.
- Non-spatial dimensions SHOULD have a chunk length of 1.
- A store chunked for time-series access SHOULD be published beside a
  display-chunked copy.
- Chunks SHOULD be 256 to 1024 samples on X and Y. A shard MAY be larger on X
  and Y.
- A shard MUST NOT span the non-spatial dimensions by a product of more than 8.

## Codecs

Every codec in the chain SHOULD have a JavaScript implementation. `blosc`,
`lz4`, `zstd`, `gzip`, `zlib`, `shuffle`, `delta`, `scale_offset`,
`transpose`, `bytes`, `crc32c`, and `sharding_indexed` qualify.

## Open questions

- The 4-chunk and 8-sample thresholds are provisional. Tests against real
  stores can move them.
- The render extension has no field that ties a `renders` entry to one
  variable of a cube. Until it has one, a `rescale` in any `renders` entry
  meets the display range rule.
- The STAC Zarr Best Practices recommend the STAC Projection extension on a
  Zarr asset. Portolan does not require it for COG or for Zarr. A change to
  that position needs to cover both formats.
