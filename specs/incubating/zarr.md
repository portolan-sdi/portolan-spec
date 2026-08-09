# Incubating — Zarr

**Status: Open. Waiting for the Zarr conventions and a reference implementation to stabilize.**

Portolan currently requires raster data to be published as COG. That remains the right format for imagery and single-timestep rasters.

Zarr is needed for a different use case: multidimensional raster data, such as data indexed by time, depth, or multiple bands as well as x/y. Several major public datasets already use Zarr, so Portolan needs a way to catalog these datasets eventually.

We are not ready to make Zarr normative yet. The conventions Portolan would need to rely on are still experimental, and there is no validator that can check a complete Zarr dataset against them.

## There is no stable "GeoZarr" specification yet

The [geozarr-spec](https://github.com/zarr-developers/geozarr-spec) repository has never released a specification. Its README says that a specification will be produced once the underlying conventions are mature enough to form a coherent suite.

The work has instead moved into separate conventions maintained by the [zarr-conventions](https://github.com/zarr-conventions) organization.

The three relevant conventions currently under active development are:

| Convention                                                     | Purpose                                  | UUID                                   |
| -------------------------------------------------------------- | ---------------------------------------- | -------------------------------------- |
| [multiscales](https://github.com/zarr-conventions/multiscales) | Resolution pyramids                      | `d35379db-88df-4056-af3a-620245f8e347` |
| [proj](https://github.com/zarr-conventions/proj)               | Coordinate reference system              | `f17cb550-5864-4468-aeb7-f3180cfb622f` |
| [spatial](https://github.com/zarr-conventions/spatial)         | Mapping array indices to x/y coordinates | `689b58e2-cf7b-45e0-9fff-9cfc0883d6b4` |

CF in Zarr, DGGS in Zarr, and TileMatrixSet are also being considered, but none currently has a stable repository.

All three active conventions are v0.1, with maturity marked as "Pilot." They explicitly warn that breaking changes are expected before v1.

A Zarr store declares conventions through its `zarr_conventions` attribute. Each entry contains a convention UUID and a `schema_url` whose version tag identifies the version. There is no separate version field.

This fits Portolan's existing model, where the schema URI is the version signal.

**For now, Portolan should therefore refer to specific Zarr conventions and UUIDs, not to "GeoZarr" as though it were a published specification.**

## Proposed direction

When Zarr support becomes normative, Portolan would require a Zarr v3 store declaring the relevant conventions and providing consolidated metadata at the store root.

The most important convention is `multiscales`.

A Zarr array without a resolution pyramid has poor browser performance when the full-resolution array is too large to load into memory. A multiscale pyramid allows clients to request an appropriate resolution instead, which is the same basic reason Portolan requires overviews in COGs.

However, simply declaring `multiscales` is not enough. The current convention requires a `layout` array but does not specify a minimum number of pyramid levels. A one-level pyramid could therefore satisfy the convention without providing a useful overview.

Portolan's COG requirements already define an explicit minimum overview depth: the pyramid must continue until the coarsest level fits within one tile.

We need to decide whether Zarr conformance should impose an equivalent minimum, or whether Portolan should wait for the multiscales convention to define one.

## Open questions

### Statistics

Portolan requires COG bands to contain embedded minimum, maximum, mean, and standard deviation values. These let clients style data without first reading the pixels.

Zarr currently has no equivalent convention. We need to decide whether Portolan requires statistics for Zarr and, if so, where they come from.

### Chunk sizing

COG internal tiles are capped at roughly a screen-sized block, conventionally 512×512. Zarr chunks serve a similar purpose.

Zarr v3 sharding can group many chunks into one object, avoiding a store containing millions of individual objects. Portolan does not yet have requirements for either chunk size or sharding.

### A Zarr store is not a file

Portolan's asset rules currently assume that an `href` resolves to a file. `file:size` and `file:checksum` describe the bytes at that location.

A Zarr `href` instead points to a store containing many objects.

We therefore need to decide whether these file properties are omitted for Zarr assets or whether Portolan defines what they mean for a store.

### STAC modeling

The media type for Zarr is `application/vnd.zarr`, but the STAC model is not settled.

The [xarray-assets](https://github.com/stac-extensions/xarray-assets) extension was deprecated and archived in June 2025. Its authors pointed toward a future `zarr` extension that does not yet exist.

The [datacube](https://github.com/stac-extensions/datacube) extension (v2.3.0) describes dimensions and variables and may provide the structure Portolan needs. Whether Portolan requires it remains open.

### Styling

Raster styling is already unresolved for COG ([#41](https://github.com/portolan-sdi/portolan-spec/issues/41), see `raster-styling.md`).

Zarr makes this more complicated because a cube may contain many dimensions and variables rather than a single fixed set of bands.

### Collection structure

A COG collection can naturally represent each scene as a STAC Item.

A single Zarr store may instead contain data that would correspond to thousands of scenes. There is no obvious equivalent item boundary.

We need to decide whether the store is represented as one collection-level asset or whether STAC Items index subsets of the store.

### Transactional stores

[Icechunk](https://icechunk.io/) provides versioning and transactions on top of Zarr and is already used for datasets that might otherwise be published as ordinary Zarr.

We have not yet determined whether an Icechunk-backed store can meet Portolan's requirements for browser-accessible data.

## When this becomes normative

This document should move into `formats.md` once:

1. the relevant Zarr conventions reach v1;
2. Portolan has an answer for statistics;
3. the STAC and asset model is defined;
4. the remaining storage requirements, such as chunking, are resolved; and
5. a validator and reference implementation can verify the resulting requirements.

As with the point-cloud format, the reference implementation should be established before the format becomes normative.
