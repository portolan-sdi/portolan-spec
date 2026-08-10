# Sample Raster COG

A small 3-band Cloud Optimized GeoTIFF used to exercise the raster path end to end, rasterio's RGB.byte.tif test fixture, derived from USGS Landsat 7 imagery over Andros Island in the Bahamas. Optimized to a COG with per-band statistics, minimum, maximum, mean, and standard deviation, embedded in the header, in UTM zone 18N (EPSG:32618).

A 791 by 718 pixel, 3-band, 8-bit image at roughly 300 meter
resolution whose georeferencing places it over Andros Island in the
Bahamas, the shallow Great Bahama Bank to its west and the deep Tongue
of the Ocean along its east coast. It is
[rasterio's](https://github.com/rasterio/rasterio) RGB.byte.tif test
fixture, derived from USGS Landsat 7 imagery per the project's
[test data notes](https://github.com/rasterio/rasterio/blob/main/tests/data/README.rst),
in the repository since rasterio's first tests in November 2013 and
the workhorse image of its README and topic guides ever since. Anyone
who has learned rasterio has seen this picture.

Here it exercises the Portolan raster path end to end, a Cloud
Optimized GeoTIFF with internal tiling, an overview level, and
per-band statistics embedded in both the STAC metadata and the GeoTIFF
header.

Agents, [AGENTS.md](./AGENTS.md) covers the nodata trap and windowed
reads.

## Quick Start

```python
import rioxarray

da = rioxarray.open_rasterio("sample-cog.tif", masked=True)
print(da)
```

The `data` asset is a Cloud Optimized GeoTIFF, so the same call against the published URL streams only the bytes it needs over HTTP range requests. Pass masked=True so nodata reads as NaN.

## Why a COG, Watching the Range Reads

A Cloud Optimized GeoTIFF serves partial reads over HTTP. Opening the
published copy with GDAL's debug output on shows it, a 64 pixel window
costs two range requests of roughly 0.4 MB, not the whole file.

```bash
CPL_DEBUG=ON gdal_translate -srcwin 0 0 64 64 \
  /vsicurl/https://data.source.coop/portolan/portolan-pipeline/portolan-reference/main/raster/sample-cog/sample-cog.tif \
  /tmp/window.tif
# VSICURL: Downloading 0-16383 ... 229376-655359
```

## Suggested Uses

Learning and testing COG access patterns, windowed reads, overview
reads, HTTP range requests, at a size where experiments cost nothing.
Its familiarity is the feature, tutorials and bug reports written
against rasterio's docs transfer directly.

## Limitations

Not an analytically useful dataset, and the documentation should be
the last place you learn that. The acquisition date and Landsat scene
id are unrecorded, the temporal extent here starts at the Landsat 7
launch in April 1999 only as an honest lower bound. Bands are
display-stretched 8-bit RGB, not calibrated reflectance, so no
conclusion about the Bahamas should be drawn from these pixels. About
a third of the image is a nodata collar from the rotated scene
footprint.

## Provenance and License

License, CC0-1.0.
Providers, rasterio (producer, licensor), Portolan SDI (host).
Original source, https://raw.githubusercontent.com/rasterio/rasterio/main/tests/data/RGB.byte.tif .
Bands, 3. CRS, EPSG:32618. Cloud-native asset, sample-cog.tif (COG).
