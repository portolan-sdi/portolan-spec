# Eurostat Electricity Prices for Household Consumers

Semi-annual electricity prices for household consumers across European countries by consumption band, tax component, and currency, Eurostat table nrg_pc_204. Non-geospatial companion table, join key is the country code column geo (NUTS-0), converted to cloud-native Parquet.

What households pay for electricity across Europe, semester by
semester since 2007. This is Eurostat table
[nrg_pc_204](https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_204/default/table),
65,412 observations covering 41 countries and territories plus the
EU27 and euro area aggregates, collected under
[Regulation (EU) 2016/1952](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32016R1952)
as consumption-weighted national average prices per six-month period.
New semesters land each April and October, and Eurostat's own
[price statistics article](https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Electricity_price_statistics)
is written from this table. It is the official record of the 2022
energy crisis, Germany's all-tax price for a typical household rose
from 0.33 to a 0.41 euro per kilowatt-hour peak in the first half of
2023.

Agents, [AGENTS.md](./AGENTS.md) decodes every dimension and carries
the aggregate-row trap.

## Quick Start

```python
import pandas as pd

df = pd.read_parquet("eurostat-electricity-prices.parquet")
print(df.head())
```

The `data` asset is plain Parquet, so pandas, DuckDB, and Polars all read it directly. Paths are relative to this directory, and the same code works against the published URL.

## Reading a Price Correctly

Every price is qualified by four dimensions, and comparisons only mean
something within a fixed combination. The band, how much the household
consumes per year, where KWH2500-4999 is the band Eurostat headlines.
The tax level, X_TAX before taxes, X_VAT before VAT, I_TAX what a
household actually pays. The currency, where EUR is nominal, NAC is
national currency, and PPS adjusts for price levels, Bulgaria's 2025-S2
price is 0.14 EUR but 0.22 PPS, and the gap is the point. And the
semester string, 2025-S2 meaning July to December 2025.

## Schema

| Column | Type | Description |
|---|---|---|
| `DATAFLOW` | varchar | Eurostat dataflow identifier, the constant ESTAT nrg_pc_204 version 1.0. |
| `LAST UPDATE` | timestamp | Frozen at one 2019 timestamp for every row of this snapshot while the data runs to 2025. Unreliable, do not derive freshness from it. |
| `freq` | varchar | Observation frequency, the constant S for semi-annual. S1 is January to June, S2 is July to December. |
| `siec` | varchar | Energy product code, the constant E7000 for electricity. |
| `nrg_cons` | varchar | Annual consumption band. KWH_LT1000, KWH1000-2499, KWH2500-4999 the headline household band, KWH5000-14999, KWH_GE15000, and TOT_KWH the weighted all-band average that exists only from 2017-S2. |
| `unit` | varchar | Unit of measure, the constant KWH. Prices are per kilowatt-hour. |
| `tax` | varchar | Tax level. X_TAX excludes all taxes and levies, X_VAT excludes VAT and recoverable taxes, I_TAX includes everything a household pays. |
| `currency` | varchar | EUR, NAC for national currency, or PPS purchasing power standard. NAC equals EUR in the euro area. |
| `geo` | varchar | Reporting country as a Eurostat NUTS-0 code, ISO 3166-1 alpha-2 except EL for Greece and UK for the United Kingdom, plus the aggregates EU27_2020 and EA. The join key to a geometry Collection. |
| `TIME_PERIOD` | varchar | Reference semester as a string, 2025-S2. Fixed format, so string ordering and MAX work. |
| `OBS_VALUE` | double | The observed electricity price in the stated currency per kilowatt-hour. |
| `OBS_FLAG` | varchar | Observation status, e estimated, p provisional, d definition differs, null for 98 percent of rows. |
| `CONF_STATUS` | varchar | Confidentiality status, entirely null in this snapshot. |

The same descriptions live in `table:columns` on the `data` asset, so tools that read STAC see them too.

## Join to Geometry

This table carries no geometry. The `geo` codes join to the Natural
Earth countries Collection in this catalog on `ISO_A2_EH`, after
remapping Eurostat's two non-ISO codes. Greece is EL and the United
Kingdom is UK. The raw ISO_A2 column would silently drop France,
Norway, and Kosovo, Natural Earth stores -99 there.

```sql
INSTALL spatial; LOAD spatial;
SELECT n.NAME, e.OBS_VALUE AS eur_per_kwh, n.geom
FROM read_parquet('eurostat-electricity-prices.parquet') e
JOIN read_parquet('../../reference/natural-earth-countries/natural-earth-countries.parquet') n
  ON (CASE e.geo WHEN 'EL' THEN 'GR' WHEN 'UK' THEN 'GB' ELSE e.geo END) = n.ISO_A2_EH
WHERE e.TIME_PERIOD = '2025-S2' AND e.nrg_cons = 'KWH2500-4999'
  AND e.tax = 'I_TAX' AND e.currency = 'EUR'
ORDER BY eur_per_kwh DESC;
```

Malta and Liechtenstein stay unmatched, the 1:110m basemap has no
polygon for them, and the EU27_2020 and EA aggregates have no
geometry by nature.

## Limitations

These are averages over suppliers and six months, not offers, Eurostat
itself notes there is no single price for electricity. One number per
country per semester, nothing sub-national. Values from the second
half of 2021 onward embed government subsidies and caps, so 2022 to
2024 understate underlying costs in heavily supported countries, and
Romania's 59 percent jump in late 2025 is a cap ending, not a market
shock. Data before 2007 lives in a separate, methodologically
incompatible table, never splice them.

## Provenance and License

License, CC-BY-4.0. Attribution, Source, Eurostat.
Providers, Eurostat (producer, licensor), Portolan SDI (host).
Original source, https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_204/?format=SDMX-CSV&compressed=false .
Rows, 65,412. Columns, 13. Cloud-native asset, eurostat-electricity-prices.parquet (Parquet).
Non-geospatial table, the bounding box is the area of interest the data pertains to, [-31.5, 34.0, 46.5, 71.5].
The upstream source is a live endpoint, so it is referenced by URL only and not archived as a source asset.
