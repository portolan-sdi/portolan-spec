# Agent Guidance, Sample Raster COG

A reference COG for exercising raster tooling, Landsat-derived RGB
over Andros Island in the Bahamas. Nothing here supports analysis, the
value is mechanical, a small well-formed COG with verified statistics.

Read the COG `data` asset with rioxarray.open_rasterio("sample-cog.tif", masked=True) or rasterio. It serves windowed reads and overviews over HTTP range requests, so read the window you need rather than the whole file. For a quick preview use the thumbnail asset.

## Quirks

- Nodata is 0 and about 33 percent of pixels are the rotated-scene
  collar. Valid data starts at 1, so always read with masking on,
  treating 0 as a measurement skews every statistic.
- There is no acquisition timestamp anywhere. The collection temporal
  start is the Landsat 7 launch date, a bound, not a date.
- Eastings run 101,985 to 339,315 meters, far west of the UTM zone 18
  central meridian. Legal values, they just look odd.

## Coordinate Reference System

EPSG:32618, WGS 84 / UTM zone 18N, a projected coordinate reference system whose coordinates are in metres.
Planar distance and area functions return metres and square metres directly, so no geodesic correction is needed. Web maps and anything joined to data in degrees need a transform to EPSG:4326 first.
The `data` asset carries the same code as `proj:code`, so this and the machine-readable metadata cannot disagree.

## Pixel Math

Pixels are 300.04 meters square, so one pixel is about 9 hectares and
pixel counts convert to area by multiplying by 300.04 squared.

## Tested Reads

Windowed read and an overview read with rasterio.

```python
import rasterio
from rasterio.windows import Window

with rasterio.open("sample-cog.tif") as src:
    window = src.read(window=Window(256, 256, 128, 128))
    overview = src.read(1, out_shape=(src.height // 2, src.width // 2))
    print(window.shape, overview.shape)
# (3, 128, 128) (359, 395), the second served from the embedded overview.
```

Masked statistics with rioxarray.

```python
import rioxarray

da = rioxarray.open_rasterio("sample-cog.tif", masked=True)
print(float(da.sel(band=3).mean()))
# 71.3, and blue > green > red across the scene, bright shallow water.
```

## Related Collections

None. This is the catalog's only raster and joins to nothing. The
upstream fixture is tagged on the source asset with its checksum, and
band statistics live in the STAC bands metadata and as GDAL
STATISTICS_* tags in the file header, written by the same build.
