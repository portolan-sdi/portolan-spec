# Sample Raster COG

A small 3-band Cloud Optimized GeoTIFF used to exercise the raster path end to end. Optimized to a COG with per-band statistics, minimum, maximum, mean, and standard deviation, embedded in the header. From the rasterio test fixtures, a 3-band raster in UTM zone 18N (EPSG:32618).

License, BSD-3-Clause.
Providers, rasterio (producer, licensor, host).
Original source, https://raw.githubusercontent.com/rasterio/rasterio/main/tests/data/RGB.byte.tif .
Bands, 3.
CRS, EPSG:32618.
Cloud-native asset, sample-cog.tif (COG).

## Open the data

The `data` asset is a Cloud Optimized GeoTIFF. Open it as an xarray array with rioxarray.

```python
import rioxarray

da = rioxarray.open_rasterio("sample-cog.tif", masked=True)
print(da)
```

Or read bands and metadata with rasterio.

```python
import rasterio

with rasterio.open("sample-cog.tif") as src:
    print(src.profile)
    band1 = src.read(1)
```
