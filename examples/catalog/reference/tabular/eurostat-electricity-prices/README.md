# Eurostat Electricity Prices for Household Consumers

Semi-annual electricity prices for household consumers across European countries by consumption band, tax component, and currency, Eurostat table nrg_pc_204. Non-geospatial companion table, join key is the country code column geo (NUTS-0), converted to cloud-native Parquet.

License, CC-BY-4.0. Attribution, Source, Eurostat.
Providers, Eurostat (producer, licensor), Portolan SDI (host).
Original source, https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_204/?format=SDMX-CSV&compressed=false .
Rows, 65412.
Columns, 13.
Non-geospatial table, spatial requirements relaxed. The bounding box is the area of interest the data pertains to, [-31.5, 34.0, 46.5, 71.5], not a geometry footprint.
Note, the upstream source is a live endpoint, so it is referenced by URL only and not archived as a source asset.

## Open the data

The `data` asset is Parquet. Open it with pandas.

```python
import pandas as pd

df = pd.read_parquet("eurostat-electricity-prices.parquet")
print(df.head())
```

Or query it in place with DuckDB.

```sql
SELECT * FROM read_parquet('eurostat-electricity-prices.parquet') LIMIT 5;
```

## Join to geometry

This table carries no geometry. Join it to `reference/natural-earth-countries` to map it.

- This table's join column, `geo`.
- Geometry collection, `reference/natural-earth-countries`, join column `ISO_A2`.

Eurostat uses NUTS-0 country codes, which match ISO 3166-1 alpha-2 for most countries but not all. Greece is EL rather than GR and the United Kingdom is UK rather than GB, so remap those two before joining if you need them.

```sql
INSTALL spatial; LOAD spatial;
SELECT t.*, g.geom
FROM read_parquet('eurostat-electricity-prices.parquet') t
JOIN read_parquet('../../reference/natural-earth-countries/natural-earth-countries.parquet') g
  ON t."geo" = g."ISO_A2";
```
