# Incubating — Zarr

## Status

Open, tracked in [#132](https://github.com/portolan-sdi/portolan-spec/issues/132).
The direction below is settled; the open questions at the end are not. Zarr is not
part of the conformance surface for the current Portolan version, and nothing here
is normative until this document graduates into
[`formats.md`](../portolan/formats.md).

## Why Zarr

Portolan requires raster data to be published as COG, which is the right format for
imagery and single-timestep rasters. Zarr covers what COG cannot: multidimensional
raster data indexed by time, depth, or band as well as x/y. Several large public
datasets already publish as Zarr, so Portolan needs a way to catalog them.

## Scope

This profile covers spatial, multiscale, raster-like Zarr datasets — the Zarr
analogue of a COG. Climate cubes organized primarily around time or depth, virtual
Zarr stores (Kerchunk, VirtualiZarr), and [Icechunk](https://icechunk.io/) are out
of scope for the initial profile. They are not excluded permanently; they need
separate requirements, and settling the spatial case first keeps this section
small enough to validate.

## Existing Specifications and Conventions

There is no published GeoZarr specification. The
[geozarr-spec](https://github.com/zarr-developers/geozarr-spec) repository has never
released a document, and the work moved into separate conventions under the
[zarr-conventions](https://github.com/zarr-conventions) organization. Portolan
therefore refers to those conventions by name and UUID, never to "GeoZarr".

Three conventions carry the geospatial semantics:

| Convention | Purpose | UUID |
| ---------- | ------- | ---- |
| [multiscales](https://github.com/zarr-conventions/multiscales) | Resolution pyramids | `d35379db-88df-4056-af3a-620245f8e347` |
| [spatial](https://github.com/zarr-conventions/spatial) | Mapping array indices to x/y coordinates | `689b58e2-cf7b-45e0-9fff-9cfc0883d6b4` |
| [proj](https://github.com/zarr-conventions/proj) | Coordinate reference system | `f17cb550-5864-4468-aeb7-f3180cfb622f` |

All three are v0.1 at "Pilot" maturity and warn that breaking changes are expected
before v1. A store declares them through its `zarr_conventions` attribute, where
each entry carries a convention UUID and a `schema_url` whose version tag identifies
the version. That matches Portolan's existing model, in which the schema URI is the
version signal.

On the STAC side, the [STAC Zarr best
practices](https://github.com/radiantearth/stac-best-practices/blob/main/best-practices-zarr.md)
define how a Zarr store is represented in STAC: asset hrefs, the `rel: store` link,
media types, and collection-vs-item modeling. The [Zarr
extension](https://github.com/stac-extensions/zarr) (v1.1.0, Proposal maturity)
supplies the asset fields a client needs to open a store. The
[Datacube](https://github.com/stac-extensions/datacube),
[Projection](https://github.com/stac-extensions/projection), and
[Raster](https://github.com/stac-extensions/raster) extensions describe dimensions
and variables, CRS and grid geometry, and per-band pixel detail respectively.
Portolan builds on all of these rather than restating them.

## Portolan Zarr Profile

When Zarr support becomes normative, Portolan will require the following.

**Zarr version.** Data MUST be provided as a Zarr v3 store. Zarr v2 stores do not
conform.

**Required conventions.** A store MUST declare the multiscales, spatial, and proj
conventions in `zarr_conventions`. All three are required together: multiscales
alone tells a client that pyramid levels exist but not what any index means on the
ground, so a client cannot place, reproject, or overlay the data without spatial
and proj.

**Consolidated metadata.** A store MUST provide consolidated metadata at its root,
so a client can read the hierarchy in one request rather than walking it.

**Multiscale depth.** A store whose full-resolution array exceeds one chunk MUST
carry a resolution pyramid, for the same reason Portolan requires internal
overviews in COGs. The exact minimum depth is an open question below.

**Statistics.** Portolan requires the same statistics for Zarr that it requires for
COG: a minimum, maximum, mean, and standard deviation per variable or band, so a
renderer can scale any data type without reading the data. No stable Zarr convention
for embedded statistics exists yet. Until one does, these SHOULD be carried in STAC
metadata, through the Raster extension or an equivalent.

**STAC representation and media types.** A Zarr asset MUST follow the STAC Zarr best
practices: its `href` references a group in the Zarr hierarchy rather than an
individual array, variables surface through the asset's `bands` array, and the store
root is identified by a link with `rel: "store"`. The base media type is
`application/vnd.zarr; version=3`. A multiscale dataset uses
`application/vnd.zarr; version=3; profile=multiscales`, which is what current STAC
tooling, including STAC Browser, reads. Assets SHOULD carry the Zarr extension
fields `zarr:consolidated`, `zarr:node_type`, and `zarr:zarr_format`.

Collection-vs-item modeling follows the same best practices. A store spanning many
places or times is a collection-level asset. A store representing a single scene or
other logical unit is an item-level asset, with each item pointing at its own store.

**Asset metadata.** `file:size` and `file:checksum` do not apply to Zarr assets.
Both describe the bytes an `href` resolves to, and a Zarr href resolves to a group
in a store of many objects rather than to a file. The [core asset
rules](../portolan/core.md#assets) otherwise apply unchanged.

**HTTP and browser accessibility.** The [Data
Storage](../portolan/core.md#data-storage) requirements apply in full. Every object
in the store MUST be reachable over HTTP with range requests and CORS enabled, not
only the metadata documents, because a browser client reads chunks directly.

## Open Questions

- **Minimum pyramid depth.** Portolan's COG requirement extends overviews until the
  coarsest level spans one tile. The multiscales convention requires a `layout`
  array but sets no minimum number of levels, so a one-level pyramid satisfies it.
  Portolan needs to decide whether to impose the COG-analogous minimum itself or
  wait for the convention to define one.
- **Chunk and shard sizing.** COG internal tiles are conventionally 512×512, and
  Zarr chunks serve a similar access-optimization purpose. Zarr v3 sharding breaks
  the one-chunk-one-object relationship, so a chunk-dimension rule no longer implies
  a request-size rule. Portolan needs to decide whether chunk dimensions or maximum
  chunk byte size are normative requirements or implementation guidance.
- **Required vs. recommended extensions.** The Zarr, Datacube, Projection, and
  Raster extensions are all candidates. Portolan needs to decide which it mandates
  and which it recommends. The statistics requirement above depends on this, since
  it currently leans on Raster.
- **Compression.** Portolan RECOMMENDS `zstd` for GeoParquet. Whether it should
  require or recommend a codec for Zarr chunks is undecided.
- **Styling.** Raster styling is unresolved for COG
  ([#41](https://github.com/portolan-sdi/portolan-spec/issues/41), see
  [`raster-styling.md`](raster-styling.md)). A Zarr store may hold many variables and
  dimensions rather than a fixed band set, which makes the question harder. This is
  blocked on the COG answer.
- **Out-of-scope formats.** Icechunk, virtual stores, and time-primary climate cubes
  need their own treatment once the spatial profile is settled.

## Path to Normative Status

This document moves into [`formats.md`](../portolan/formats.md) once:

1. the multiscales, spatial, and proj conventions reach v1;
2. the open questions above are answered, in particular pyramid depth and the
   required extension set;
3. a stable home for statistics exists, whether a Zarr convention or a settled STAC
   representation; and
4. a validator and reference implementation can verify the resulting requirements.

As with the point-cloud format, the reference implementation comes before the format
becomes normative.
