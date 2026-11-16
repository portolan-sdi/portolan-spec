# Agent guidance, sample raster scenes

A reference for the multi-scene raster layout, sixteen Landsat-derived
RGB scenes over Andros Island in the Bahamas. Do not use the scenes
for analysis.

Find scenes with the item mirror, read_parquet('items.parquet') in DuckDB or GeoPandas, one row for each Item. Then read the COG `data` asset of the Item you need with rasterio or rioxarray. Do not fetch each Item JSON to search. For a quick preview use the thumbnail asset.

## Quirks

- The Collection has no `data` asset. The pixels are in the `data`
  asset of each Item.
- Nodata is 0 in each scene. Read with masking on.
- The Item geometry is the valid-data footprint, so the corner scenes
  do not fill their grid cell.
- Each Item has `start_datetime` and `end_datetime` and a null
  `datetime`. The range bounds the acquisition date, which upstream
  does not record.

## Coordinate reference system

EPSG:32618, WGS 84 / UTM zone 18N, a projected coordinate reference system whose coordinates are in metres.
Pixel size is in metres, so cell size and any distance read off the grid are already in metres. Web maps need a warp to EPSG:3857, and joining to data in degrees needs EPSG:4326 first.
The `data` asset of each Item has the same code as `proj:code`.

## Tested reads

Count the scenes and read their footprints from the item mirror.

```python
import geopandas as gpd

items = gpd.read_parquet("items.parquet")
print(len(items), items.total_bounds.round(2))
```

Read one scene with masking on.

```python
import rioxarray

da = rioxarray.open_rasterio(
    "sample-scenes-r2c2/sample-scenes-r2c2.tif", masked=True)
print(da.shape)
```

## Related collections

[Sample Raster COG](../sample-cog/AGENTS.md) holds the same image as
one COG with no Items. Use it for the single-file raster layout.
