# Incubating — Zarr

## Status

Open, tracked in [#132](https://github.com/portolan-sdi/portolan-spec/issues/132).

The direction below is settled; the open questions at the end are not. Zarr is not part of the conformance surface for the current Portolan version. Nothing in this document is normative until the profile graduates into [`formats.md`](../portolan/formats.md).

## Why Zarr

Portolan requires raster data to be published as COG, which is the right format for imagery and single-timestep rasters. Zarr supports raster datasets that COG does not represent naturally, particularly multidimensional data indexed by dimensions such as time or depth in addition to x/y.

Several large public datasets already use Zarr, so Portolan needs a way to catalog these datasets while preserving the same cloud-native and browser-oriented access that motivates its COG requirements.

The goal is not simply to recognize geospatial Zarr. Portolan should require a Zarr representation that provides the same basic web-access property that motivates its COG requirements: a client can display a large raster at different zoom levels without fetching the full-resolution dataset.

## Scope

This profile covers spatial, multiscale, raster-like Zarr datasets: the Zarr analogue of a COG.

Climate cubes organized primarily around time or depth, virtual Zarr stores such as Kerchunk and VirtualiZarr, and transactional stores such as Icechunk are not addressed by the initial profile. They are not excluded permanently; they need separate requirements. Settling the spatial raster case first keeps this profile small enough to validate and implement.

## Existing Specifications and Conventions

There is no published GeoZarr specification. The [geozarr-spec](https://github.com/zarr-developers/geozarr-spec) repository has not released a specification, and the work has moved into separate conventions under the [zarr-conventions](https://github.com/zarr-conventions) organization.

Portolan therefore refers to the individual conventions rather than to "GeoZarr" as though it were a published specification.

Three conventions provide the geospatial semantics required by this profile:

| Convention                                                     | Purpose                                  | UUID                                   |
| -------------------------------------------------------------- | ---------------------------------------- | -------------------------------------- |
| [multiscales](https://github.com/zarr-conventions/multiscales) | Resolution pyramids                      | `d35379db-88df-4056-af3a-620245f8e347` |
| [spatial](https://github.com/zarr-conventions/spatial)         | Mapping array indices to x/y coordinates | `689b58e2-cf7b-45e0-9fff-9cfc0883d6b4` |
| [proj](https://github.com/zarr-conventions/proj)               | Coordinate reference system              | `f17cb550-5864-4468-aeb7-f3180cfb622f` |

All three are currently v0.1 at "Pilot" maturity, and all warn that breaking changes are expected before v1. A store declares them through its `zarr_conventions` attribute. Each entry carries a convention UUID and a `schema_url` whose version identifies the convention version. This matches Portolan's existing model, in which a versioned schema URI is the version signal.

The three conventions serve different purposes and are required together. `multiscales` describes the resolution pyramid, while `spatial` and `proj` tell a client how to interpret and place those arrays. A multiscale hierarchy without spatial and CRS information is not sufficient for a geospatial client to place, reproject, or overlay the data.

On the STAC side, the [STAC Zarr best practices](https://github.com/radiantearth/stac-best-practices/blob/main/best-practices-zarr.md) define how Zarr stores, groups, arrays, bands, and multiscale datasets are represented in STAC. They cover asset hrefs, the `rel: store` relationship, media types, and collection-versus-item modeling.

The [STAC Zarr extension](https://github.com/stac-extensions/zarr) provides metadata about the Zarr store, including whether metadata is consolidated, whether an asset points to a group or array, and which Zarr format it uses. It is currently v1.1.0 at Proposal maturity.

The [Datacube](https://github.com/stac-extensions/datacube), [Projection](https://github.com/stac-extensions/projection), and [Raster](https://github.com/stac-extensions/raster) extensions provide additional STAC metadata for multidimensional variables and dimensions, spatial reference and grid geometry, and raster data respectively.

Portolan should build on these existing specifications and extensions rather than define parallel metadata models.

## Portolan Zarr Profile

When Zarr support becomes normative, Portolan will require the following.

### Zarr version

Data MUST be provided as a Zarr v3 store. Zarr v2 stores do not conform.

### Required conventions

A store MUST declare the `multiscales`, `spatial`, and `proj` conventions in `zarr_conventions`. All three are required together.

`multiscales` provides the resolution pyramid needed for efficient zoomed-out access. `spatial` describes how array indices map to spatial coordinates, and `proj` identifies the coordinate reference system. Together they provide the information a client needs to interpret and display the dataset geographically.

### Consolidated metadata

A store MUST provide consolidated metadata at its root so a client can discover the Zarr hierarchy without walking the store's metadata objects individually.

### Multiscale access

Portolan requires a multiscale pyramid for large raster datasets for the same reason it requires internal overviews in COGs: a client should be able to display the dataset at lower zoom levels without fetching full-resolution pixels.

Portolan sets no minimum pyramid depth. The multiscales convention requires a non-empty `layout` and prescribes neither a level count nor a downsampling factor, and renderers follow it. The GeoZarr layout schema in [`@developmentseed/deck.gl-zarr`](https://github.com/developmentseed/deck.gl-raster/blob/main/packages/geozarr/src/schemas.ts) validates `layout` with `min(1)`, its tileset derives the available zoom range from `levels.length`, and [`zarr-viewer`](https://github.com/source-cooperative/zarr-viewer/blob/main/src/zarr/multiscale.ts) accepts a one-level layout, rejecting only an empty one. Published datasets vary widely: the Fields of The World global predictions carry fourteen levels and Meta CHM v2 carries seven, while renderers also handle stores that declare no pyramid at all, such as the AlphaEarth Foundations mosaic. Any fixed Portolan level count would be arbitrary, so depth stays with the producer.

### Storage layout

Portolan sets no normative chunk or shard requirements. Chunk shape governs how a client reads an array, and Zarr v3 sharding groups chunks into one stored object to keep a store's object count manageable. Both are workload-dependent, and the [Cloud-Native Geospatial Formats Guide](https://guide.cloudnativegeo.org/zarr/intro.html) describes them without prescribing dimensions or byte sizes. Portolan follows that guidance: chunk and shard sizing belongs in conversion defaults and best-practice material, not in the conformance surface.

### STAC representation and media types

A Zarr asset follows the [STAC Zarr best practices](https://github.com/radiantearth/stac-best-practices/blob/main/best-practices-zarr.md). Two points are requirements here: an asset `href` MUST identify a Zarr group rather than an individual array, and variables MUST be exposed through the asset's `bands` rather than as separate assets. The store root SHOULD carry a link with `rel: "store"`, which is the level the best practices set.

That document is guidance rather than a specification, and it is still moving: it dates from the October 2025 STAC sprint, describes link templates rather than asset templates, and marks the media-type `profile` parameter as not yet official. Portolan states the requirements it depends on rather than deferring to the document wholesale.

Zarr v3 assets use the media type `application/vnd.zarr; version=3`. A multiscale asset uses `application/vnd.zarr; version=3; profile=multiscales`.

Portolan requires individual STAC fields, not whole extensions. An extension is a container, and requiring all of one pulls in fields Portolan has no reason to demand.

Which extensions are required, recommended, or optional is set by the [Portolan STAC Profile](../../stac/), not restated here. It lists Projection as MAY and Raster as MUST where band-level detail is provided. This profile adds no Zarr-specific override: the required `proj` convention already carries the CRS inside the store, so a STAC-side CRS requirement would be Portolan-wide policy rather than a Zarr one.

`zarr:consolidated` and `zarr:node_type` SHOULD be present, because they tell a client whether the hierarchy is readable in one request and whether an href resolves to a group or an array. `zarr:zarr_format` is not required, since the media type already carries the format.

Datacube fields describe dimensions and variables for stores that are datacubes. Neither Datacube nor the Zarr extension appears in the STAC Profile today, and listing them is a profile-level decision.

Collection-versus-item modeling follows the STAC Zarr best practices. A store containing a dataset spanning multiple places or times may be represented at the collection level. A store representing a single scene or other logical unit may be represented at the item level.

### Asset metadata

`file:size` and `file:checksum` do not apply to Zarr group assets. Those fields describe the bytes an asset's `href` resolves to, whereas a Zarr asset href identifies a group within a store rather than a single file.

The other Core asset rules apply unchanged.

### HTTP and browser accessibility

The [Core Data Storage requirements](../portolan/core.md#data-storage) apply in full. A Portolan Zarr store MUST be readable directly by browser-based clients over HTTP, including the metadata and chunk objects required to access the data.

The HTTP requirements for range requests, HEAD requests, and CORS therefore apply to the Zarr objects that a client needs to read the store.

## Open Questions

* **Rendering metadata.** Portolan requires COGs to carry per-band statistics so a renderer can scale data without reading pixels. This profile states no equivalent Zarr requirement: no stable Zarr convention defines where such statistics live, and browser renderers already scale Zarr data without them. Whether any rendering metadata belongs in STAC for Zarr can be settled once a convention exists or a concrete rendering gap appears.

* **Compression.** Compression is an implementation choice unless Portolan identifies a concrete interoperability or access requirement. If a default is useful, the CLI can recommend a codec in the Conversion Defaults guidance rather than making it a conformance requirement.

* **Styling.** Raster styling remains unresolved for COG ([#41](https://github.com/portolan-sdi/portolan-spec/issues/41), see `raster-styling.md`). Zarr can contain multiple variables and dimensions rather than a fixed set of bands, so its styling model may require additional work. Zarr-specific styling requirements should follow the resolution of the general raster styling question rather than being designed independently here.

* **Out-of-scope stores and datasets.** Transactional and virtual Zarr stores, including Icechunk, Kerchunk, and VirtualiZarr, and climate cubes organized primarily around non-spatial dimensions need separate treatment. Their compatibility with the initial profile can be evaluated after the spatial raster case is settled.

## Path to Normative Status

This document moves into [`formats.md`](../portolan/formats.md) once:

1. the `multiscales`, `spatial`, and `proj` conventions reach stable versions suitable for Portolan to depend on;
2. the remaining open questions above are settled; and
3. a validator and reference implementation can verify the resulting requirements.

Implementation defaults such as chunking, sharding, compression, and multiscale construction parameters belong in the Portolan conversion and best-practices guidance unless they prove necessary for conformance.

As with the other Portolan formats, the reference implementation should be established before the format becomes normative.
