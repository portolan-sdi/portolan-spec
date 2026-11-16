# Sample raster scenes

Sixteen small Cloud Optimized GeoTIFF scenes, modeled as STAC Items, with a stac-geoparquet item mirror. The scenes are a 4 by 4 grid cut from rasterio's RGB.byte.tif test fixture, derived from USGS Landsat 7 imagery over Andros Island in the Bahamas, in UTM zone 18N (EPSG:32618).

The multi-scene raster layout in its smallest form. The source image
is [rasterio's](https://github.com/rasterio/rasterio) RGB.byte.tif
test fixture, the same file as the
[Sample Raster COG](../sample-cog/README.md) Collection. Here a 4 by
4 grid cuts it into sixteen scenes of about 198 by 180 pixels.

The Collection has two parts.

- Each scene is a STAC Item in its own directory, with its Cloud
  Optimized GeoTIFF as the `data` asset. The Item geometry is the
  valid-data footprint of the scene, so a corner scene has a
  triangle or a trapezoid, not the grid cell.
- `items.parquet` is the item mirror, a stac-geoparquet copy of the
  sixteen Items with the `collection-mirror` role. The rows are in
  Hilbert curve order.

Agents, [AGENTS.md](./AGENTS.md) covers how to search the scenes.

## Quick start

```python
import geopandas as gpd

items = gpd.read_parquet("items.parquet")
print(items[["id", "geometry"]].head())
```

`items.parquet` is the item mirror, a stac-geoparquet file with one row for each Item, so one read returns every scene footprint. Each scene is a Cloud Optimized GeoTIFF in its own Item directory. Paths are relative to this directory, and the same code works against the published URL.

## Find the scenes over a point

One read of the item mirror is enough for a spatial search. This query
returns the scenes whose footprint covers a point on Andros Island.

```sql
INSTALL spatial; LOAD spatial;
SELECT id, assets.data.href AS cog
FROM read_parquet('items.parquet')
WHERE ST_Contains(geometry, ST_Point(-77.9, 24.7));
```

## Limitations

A layout example, not imagery for analysis. The scenes are small
cuts of one 300 meter test image. The acquisition date is unrecorded
upstream, so each Item has a time range and no `datetime`. The range
starts at the Landsat 7 launch and ends when the file entered the
rasterio repository.

## Provenance and license

License, CC0-1.0.
Providers, rasterio (producer, licensor), Portolan SDI (host).
Original source, https://raw.githubusercontent.com/rasterio/rasterio/main/tests/data/RGB.byte.tif .
Scenes, 16, one COG for each Item. Bands, 3. CRS, EPSG:32618. Item mirror, items.parquet (stac-geoparquet).
