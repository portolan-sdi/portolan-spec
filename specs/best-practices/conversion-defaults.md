# Conversion Defaults

This is guidance, not conformance. What a Portolan catalog must contain lives in
[`specs/portolan/`](../portolan/); this page records the settings the Portolan CLI
reaches for when it converts source data into cloud-native form. Most are borrowed
from [rio-cogeo](https://cogeotiff.github.io/rio-cogeo/) and GDAL. A file produced
with different settings still conforms as long as it meets the requirements in the
spec, so treat these as sensible starting points rather than rules.

## Raster (COG)

The [Raster section](../portolan/formats.md#raster) requires a valid COG with
internal overviews and embedded statistics. Within that envelope, the CLI picks
these defaults.

- **Compression: DEFLATE.** Lossless and readable everywhere, a safe default across
  data types. `zstd` and `LZW` are fine alternatives where the reader supports them.
  Reach for lossy `JPEG` or `WEBP` only for visual imagery where some pixel loss is
  acceptable, never for measured or categorical data.
- **Predictor: horizontal for integer, floating-point for float.** Predictor `2`
  (horizontal differencing) shrinks integer rasters, and predictor `3` suits
  floating-point data. Skip the predictor for RGB byte imagery and already-compressed
  inputs, where it adds nothing.
- **Internal tiles: 512×512.**
  [OGC 21-026](https://docs.ogc.org/is/21-026/21-026.html#optimized_geotiff-requirements-class)
  asks for square tiles no larger than a screen viewport and recommends a power of
  two: 256, 512, or 1024. 512 sits in the middle and is the tile size the overview
  requirement keys off, so a raster wider or taller than 512 pixels needs overviews.
- **Overview resampling: nearest for categorical, averaging for continuous.**
  `nearest` preserves exact class values and is the CLI default. For continuous
  imagery, `average` or `bilinear` produce smoother zoomed-out views. Choose by what
  the pixels mean.

## Partitioning

When a file is large enough to partition, follow the sizing guidance already in the
[Partitioned Collections section](../portolan/formats.md#partitioned-collections):
consider partitioning past roughly 2 GB, target 200 MB to 1 GB per file, and keep
row groups under 150,000 rows. Fewer, larger files read faster in DuckDB than many
small ones.

## Thumbnails

Core requires a `thumbnail`-role asset on every Collection. The CLI renders it as a
small PNG that reads as a real map: projected to Web Mercator at the data's true
aspect ratio over a light basemap, rather than stretched into a square. A few hundred
pixels on the long edge is plenty. The thumbnail is a preview to help someone
recognize the data at a glance, not a substitute for opening it.
