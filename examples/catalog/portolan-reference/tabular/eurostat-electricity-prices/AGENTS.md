# Agent Guidance, Eurostat Electricity Prices for Household Consumers

Semi-annual household electricity prices, one row per combination of
consumption band, tax level, currency, country, and semester, verified
unique on those five. Filter all five dimensions before comparing
anything. The headline combination is nrg_cons = 'KWH2500-4999',
tax = 'I_TAX', currency = 'EUR'.

Query the Parquet `data` asset in place with DuckDB, read_parquet('eurostat-electricity-prices.parquet'), or load it with pandas.

## Quirks

- EU27_2020 and EA sit in geo alongside countries, so unfiltered
  rankings place the EU average mid-table as if it were a country.
  Exclude them for country-level analysis.
- The LAST UPDATE column is frozen at one 2019 timestamp on all 65,412
  rows of this snapshot while data runs to 2025-S2. It also has a space
  in its name, quote it as "LAST UPDATE".
- The panel is ragged. The UK stops after 2020-S1, Ukraine after
  2021-S1, Iceland lags a semester, and 2007-S1 has only 8 reporters.
- TOT_KWH is itself a weighted average of the five bands and exists
  only from 2017-S2. Never mix it into a band aggregate.
- For euro-area countries NAC duplicates EUR, so counting rows across
  currencies triple-counts observations.
- About 2 percent of rows carry flags, e estimated, p provisional, d
  definition differs, and provisional values are revised in later
  snapshots, so this fixed copy can disagree with the live API on
  recent semesters.

## Tested Queries

Latest prices ranked, aggregates excluded.

```sql
SELECT geo, OBS_VALUE AS eur_per_kwh
FROM read_parquet('eurostat-electricity-prices.parquet')
WHERE nrg_cons = 'KWH2500-4999' AND tax = 'I_TAX' AND currency = 'EUR'
  AND TIME_PERIOD = (SELECT max(TIME_PERIOD) FROM read_parquet('eurostat-electricity-prices.parquet'))
  AND geo NOT IN ('EU27_2020', 'EA')
ORDER BY eur_per_kwh DESC;
-- Ireland 0.4042, Germany 0.3869, Belgium 0.3499, down to Turkey 0.0636.
```

A time series with real dates from the semester strings.

```sql
SELECT TIME_PERIOD,
       make_date(CAST(TIME_PERIOD[1:4] AS INT),
                 CASE WHEN TIME_PERIOD LIKE '%S1' THEN 1 ELSE 7 END, 1) AS period_start,
       OBS_VALUE AS eur_per_kwh
FROM read_parquet('eurostat-electricity-prices.parquet')
WHERE geo = 'DE' AND nrg_cons = 'KWH2500-4999' AND tax = 'I_TAX'
  AND currency = 'EUR'
ORDER BY TIME_PERIOD;
-- 38 semesters, 0.2025 in 2007-S1, peaking at 0.4125 in 2023-S1.
```

The tax ladder, what levies add.

```sql
SELECT tax, OBS_VALUE
FROM read_parquet('eurostat-electricity-prices.parquet')
WHERE geo = 'EU27_2020' AND TIME_PERIOD = '2025-S2'
  AND nrg_cons = 'KWH2500-4999' AND currency = 'EUR'
ORDER BY OBS_VALUE;
-- X_TAX 0.2059, X_VAT 0.2456, I_TAX 0.2896, all matching Eurostat's
-- published article to four decimals.
```

## Related Collections

`reference/natural-earth-countries` is the geometry partner, join
recipe in the README of this Collection. Sibling Eurostat tables
outside this catalog, nrg_pc_205 for non-household prices and
nrg_pc_204_c for price components, share the same dimension scheme.
Converted from Eurostat's SDMX-CSV API output, a live endpoint, to
Parquet with DuckDB on July 21, 2026.
