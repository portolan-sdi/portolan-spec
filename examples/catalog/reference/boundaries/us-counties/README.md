# United States Counties (2023, 1:500k)

County and equivalent boundaries for the United States, the 2023 cartographic boundary file at 1:500,000 from the US Census Bureau, generalized for small-scale mapping. Republished as cloud-native GeoParquet alongside the original zipped Shapefile.

License, CC0-1.0.
Providers, U.S. Census Bureau (producer, licensor), Portolan SDI (host).
Original source, https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip .
Features, 3235.
Cloud-native asset, us-counties.parquet (GeoParquet).

## Open the data

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column for fast web-client pruning. Read it with a recent GeoPandas built on pyarrow 24 or newer.

```python
import geopandas as gpd

gdf = gpd.read_parquet("us-counties.parquet")
print(gdf.head())
```

Or query it in place with a recent DuckDB spatial.

```sql
INSTALL spatial; LOAD spatial;
SELECT * FROM read_parquet('us-counties.parquet') LIMIT 5;
```
