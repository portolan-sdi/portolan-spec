# Incubating Specs

This folder holds ad-hoc specifications that are being formalized but are not yet
stable enough to be normative in [`specs/portolan/`](../portolan/). They range from
requirements whose exact encoding is still settling to whole areas (like point
clouds) that are waiting on a reference implementation.

Content here is **not** part of the conformance surface for the current Portolan
version. When a topic stabilizes, it graduates into `core.md` or `formats.md` and
its incubating doc is removed. Debate happens in GitHub issues and PRs.

| Doc | Status |
|-----|--------|
| [`raster-styling.md`](raster-styling.md) | Open — how raster styles are expressed ([#41](https://github.com/portolan-sdi/portolan-spec/issues/41)) |
| [`point-cloud.md`](point-cloud.md) | Deferred — awaiting a COPC reference implementation |
| [`zarr.md`](zarr.md) | Open — multidimensional raster; awaiting Zarr convention stability and a reference implementation |
| [`geotiff-stats-headers.md`](geotiff-stats-headers.md) | Encoding detail for the (normative) COG statistics requirement |
| [`stac-geoparquet.md`](stac-geoparquet.md) | Partly graduated — raster item mirrors are normative; STAC-GeoParquet mirrors of collections still open ([#72](https://github.com/portolan-sdi/portolan-spec/issues/72)) |
