# Incubating — Zarr

**Status: open, awaiting convention stability and a reference implementation.**

Portolan requires raster data as COG. That requirement holds for imagery and
single-timestep rasters, and it will keep holding. Zarr addresses what COG cannot
express: a multidimensional cube indexed by time, band, or depth as well as by x
and y. Several large public datasets are already published this way, so Portolan
needs a defined path for cataloging them.

Two things must settle before that path becomes normative. The conventions Portolan
would cite are pre-stable, and no validator can check them yet.

## "GeoZarr" Does Not Name a Document

The [geozarr-spec](https://github.com/zarr-developers/geozarr-spec) repository has
never released a version. Its README states the specification "will be produced once
a set of mature conventions forms a coherent and recommended suite." Work moved to
individual conventions published under the
[zarr-conventions](https://github.com/zarr-conventions) organization.

Three are under active development:

| Convention | Purpose | UUID |
|------------|---------|------|
| [multiscales](https://github.com/zarr-conventions/multiscales) | Resolution pyramids | `d35379db-88df-4056-af3a-620245f8e347` |
| [proj](https://github.com/zarr-conventions/proj) | Coordinate reference system | `f17cb550-5864-4468-aeb7-f3180cfb622f` |
| [spatial](https://github.com/zarr-conventions/spatial) | Array index to x/y coordinate mapping | `689b58e2-cf7b-45e0-9fff-9cfc0883d6b4` |

CF in Zarr, DGGS in Zarr, and TileMatrixSet are under consideration and have no
stable repository.

All three active conventions are at v0.1 with maturity "Pilot." Each warns that
breaking changes should be expected before v1, anticipated before the end of 2026.

A convention declares itself through an entry in the `zarr_conventions` array in the
store's attributes, carrying its UUID and a `schema_url` whose tag conveys the
version. There is no separate version field. Portolan already treats a schema URI as
the sole version signal, so the two models compose without translation.

The practical consequence: a Portolan requirement must cite conventions and UUIDs,
not "GeoZarr." A catalog claiming GeoZarr conformance today names no checkable
document.

## Direction

Zarr raster data would be provided as a Zarr v3 store declaring all three
conventions, with consolidated metadata at the store root so a reader retrieves the
hierarchy in one request.

Multiscales carries the weight. Without a resolution pyramid, a Zarr store performs
in a browser the way a plain GeoTIFF does: usable only when the whole array fits in
memory. With one, it approaches COG. This is the same requirement Portolan already
imposes on COG, where internal overviews are raised from a validator warning to a
conformance failure. The reasoning transfers directly.

Declaring the convention is weaker than satisfying it. The multiscales convention
requires a `layout` array but sets no floor on how many levels it contains, so a
single-level pyramid declares conformance while delivering nothing. Portolan's COG
rule states the floor explicitly: overviews extend until the coarsest level spans one
tile. Whether Portolan restates that floor for multiscales, or waits for the
convention to define it, is open.

## Open Questions

**Statistics.** Portolan requires every COG band to carry embedded minimum, maximum,
mean, and standard deviation so a renderer can scale any data type without reading
pixels. Zarr has no equivalent convention. Without one, a client cannot colorize a
float array it has never opened. Nothing in the current suite fills this gap.

**Chunk sizing.** The COG rule caps internal tiles at roughly a screen viewport,
512×512 by convention. Zarr chunks serve the same role, and v3 sharding lets many
chunks share one object, which keeps stores from fragmenting into millions of keys.
Neither has a stated target here.

**A store is not a file.** Portolan asset rules assume an href resolving to bytes.
`file:size` and `file:checksum` MUST match the bytes the href resolves to, and a
Zarr href points at a store root holding thousands of objects. Either these fields
are undefined for Zarr assets, or Portolan defines what they cover.

**STAC modeling.** The media type is `application/vnd.zarr`. Beyond that the ground
is unsettled. The [xarray-assets](https://github.com/stac-extensions/xarray-assets)
extension, which carried the reader hints most published Zarr assets use, was
deprecated and archived in June 2025; its authors point to a `zarr` extension that
does not yet exist. The [datacube](https://github.com/stac-extensions/datacube)
extension (v2.3.0) describes dimensions and variables and is the likely vehicle for
declaring cube structure, but whether Portolan requires it is undecided.

**Styling.** Raster styling is unresolved for COG already
([#41](https://github.com/portolan-sdi/portolan-spec/issues/41), see
[`raster-styling.md`](raster-styling.md)). Zarr inherits that gap and widens it: a
cube has no single band set to style.

**Collection structure.** A COG scene collection models each scene as an item. One
Zarr store often holds what would otherwise be thousands of scenes, so the item
boundary has no obvious analogue. Whether a store is one collection-level asset, or
items index slices of it, needs deciding.

**Transactional stores.** [Icechunk](https://icechunk.io/) adds versioning and
transactions over Zarr and is in use for datasets that would otherwise be plain Zarr.
Whether such a store can satisfy Portolan's browser-reachable access requirements is
unexamined.

## Graduation

This document graduates into `formats.md` when the three conventions reach v1, a
statistics answer exists, and a validator can check convention declarations against
store contents. Following the precedent set for point clouds, a reference
implementation comes first.
