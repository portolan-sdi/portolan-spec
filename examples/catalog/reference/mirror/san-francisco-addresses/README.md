# San Francisco Addresses (EAS)

Point addresses from the City and County of San Francisco Enterprise Addressing System, a 5,000-feature extract of the official DataSF open data layer, converted to cloud-native GeoParquet with a PMTiles visualization. The source asset points at the full live DataSF layer.

License, PDDL-1.0.
Providers, City and County of San Francisco (producer, licensor), DataSF (processor), Portolan SDI (host).
Original source, https://data.sfgov.org/resource/ramy-di5m.geojson?$limit=5000 .
Features, 5000.
Cloud-native asset, san-francisco-addresses.parquet (GeoParquet).
Note, the upstream source is a live endpoint, so the source checksum reflects the copy fetched at build time.

## Open the data

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column for fast web-client pruning. Read it with a recent GeoPandas built on pyarrow 24 or newer.

```python
import geopandas as gpd

gdf = gpd.read_parquet("san-francisco-addresses.parquet")
print(gdf.head())
```

Or query it in place with a recent DuckDB spatial.

```sql
INSTALL spatial; LOAD spatial;
SELECT * FROM read_parquet('san-francisco-addresses.parquet') LIMIT 5;
```
