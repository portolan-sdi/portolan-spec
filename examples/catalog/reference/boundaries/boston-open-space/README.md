# Boston Open Space

City of Boston open spaces and parks, playgrounds, athletic fields, conservation land, and cemeteries, 1,012 polygons from the City of Boston GIS open data platform. Official primary source, republished as cloud-native GeoParquet with a PMTiles visualization and MapLibre styles.

License, PDDL-1.0.
Providers, City of Boston (producer, licensor, host).
Original source, https://opendata.arcgis.com/api/v3/datasets/2868d370c55d4d458d4ae2224ef8cddd_7/downloads/data?format=shp&spatialRefId=4326 .
Features, 1012.
Cloud-native asset, boston-open-space.parquet (GeoParquet).
Note, the upstream source is a live endpoint, so the source checksum reflects the copy fetched at build time.

## Open the data

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column for fast web-client pruning. Read it with a recent GeoPandas built on pyarrow 24 or newer.

```python
import geopandas as gpd

gdf = gpd.read_parquet("boston-open-space.parquet")
print(gdf.head())
```

Or query it in place with a recent DuckDB spatial.

```sql
INSTALL spatial; LOAD spatial;
SELECT * FROM read_parquet('boston-open-space.parquet') LIMIT 5;
```
