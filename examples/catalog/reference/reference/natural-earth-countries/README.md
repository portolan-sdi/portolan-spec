# Natural Earth Countries (1:110m)

World country boundaries at 1:110m scale from Natural Earth, the public domain reference basemap maintained by NACIS. Republished as cloud-native GeoParquet alongside the original zipped Shapefile.

License, CC0-1.0.
Providers, Natural Earth (producer, licensor), Portolan SDI (host).
Original source, https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip .
Features, 177.
Cloud-native asset, natural-earth-countries.parquet (GeoParquet).

## Open the data

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column for fast web-client pruning. Read it with a recent GeoPandas built on pyarrow 24 or newer.

```python
import geopandas as gpd

gdf = gpd.read_parquet("natural-earth-countries.parquet")
print(gdf.head())
```

Or query it in place with a recent DuckDB spatial.

```sql
INSTALL spatial; LOAD spatial;
SELECT * FROM read_parquet('natural-earth-countries.parquet') LIMIT 5;
```
