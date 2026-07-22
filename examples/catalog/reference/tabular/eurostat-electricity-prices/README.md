# Eurostat Electricity Prices for Household Consumers

Semi-annual electricity prices for household consumers across European countries by consumption band, tax component, and currency, Eurostat table nrg_pc_204. Non-geospatial companion table, join key is the country code column geo (NUTS-0), converted to cloud-native Parquet.

License, CC-BY-4.0. Attribution, Source, Eurostat.
Providers, Eurostat (producer, licensor, host).
Original source, https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_204/?format=SDMX-CSV&compressed=false .
Rows, 65412.
Columns, 13.
Non-geospatial table, spatial requirements relaxed.
Note, the upstream source is a live endpoint, so the source checksum reflects the copy fetched at build time.

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
