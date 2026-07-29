# Netherlands Provinces

The 12 provinces of the Netherlands, administrative boundaries from the Dutch national spatial data infrastructure PDOK, derived from the Kadaster BRK Bestuurlijke Gebieden. Republished as cloud-native GeoParquet with a PMTiles visualization and categorical, labeled MapLibre styles.

License, CC-BY-4.0. Attribution, Kadaster / PDOK.
Providers, Kadaster (producer, licensor), PDOK (processor), Portolan SDI (host).
Original source, https://service.pdok.nl/kadaster/brk-bestuurlijke-gebieden/atom/downloads/BestuurlijkeGebieden_2026.gpkg .
Features, 12.
Cloud-native asset, netherlands-provinces.parquet (GeoParquet).

## Open the data

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column for fast web-client pruning. Read it with a recent GeoPandas built on pyarrow 24 or newer.

```python
import geopandas as gpd

gdf = gpd.read_parquet("netherlands-provinces.parquet")
print(gdf.head())
```

Or query it in place with a recent DuckDB spatial.

```sql
INSTALL spatial; LOAD spatial;
SELECT * FROM read_parquet('netherlands-provinces.parquet') LIMIT 5;
```
