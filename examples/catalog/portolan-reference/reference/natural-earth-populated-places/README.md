# Natural Earth Populated Places (1:50m)

Point locations of populated places, cities and towns, at 1:50m scale from Natural Earth. Public domain reference points, republished as cloud-native GeoParquet alongside the original zipped Shapefile.

License, CC0-1.0.
Providers, Natural Earth (producer, licensor), Portolan SDI (host).
Original source, https://naciscdn.org/naturalearth/50m/cultural/ne_50m_populated_places.zip .
Features, 1251.
Cloud-native asset, natural-earth-populated-places.parquet (GeoParquet).

## Open the data

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column for fast web-client pruning. Read it with a recent GeoPandas built on pyarrow 24 or newer.

```python
import geopandas as gpd

gdf = gpd.read_parquet("natural-earth-populated-places.parquet")
print(gdf.head())
```

Or query it in place with a recent DuckDB spatial.

```sql
INSTALL spatial; LOAD spatial;
SELECT * FROM read_parquet('natural-earth-populated-places.parquet') LIMIT 5;
```
