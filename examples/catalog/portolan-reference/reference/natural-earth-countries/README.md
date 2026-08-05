# Natural Earth Countries (1:110m)

World country boundaries at 1:110m scale from Natural Earth, the public domain reference basemap maintained by NACIS. Republished as cloud-native GeoParquet alongside the original zipped Shapefile.

[Natural Earth](https://www.naturalearthdata.com) is the public domain
reference map dataset that Nathaniel Vaughn Kelso and Tom Patterson
started in 2009 and maintain with volunteer cartographers under
[NACIS](https://nacis.org). This collection carries its 1:110m countries
theme, version 5.1.1 from May 2022, and holds 177 country polygons with
171 attribute columns of names in 26 languages, ISO codes, population
and GDP estimates from 2019, and cartographic styling hints. It is the
geometry behind [world-atlas](https://github.com/topojson/world-atlas)
and with that most of the world choropleths on the web.

Boundaries follow Natural Earth's
[de facto policy](https://www.naturalearthdata.com/about/disputed-boundaries-policy/),
showing who controls territory rather than legal claims, so Somaliland
and Northern Cyprus appear as their own rows. The 34 FCLASS point-of-view
columns added in December 2021 let a map follow a specific national
worldview instead.

Agents, read [AGENTS.md](./AGENTS.md) first. It carries the join keys,
the sentinel-value traps, and tested queries.

## Quick Start

```python
import geopandas as gpd

gdf = gpd.read_parquet("natural-earth-countries.parquet")
print(gdf.head())
```

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column, so it needs a GeoPandas built on pyarrow 24 or newer. DuckDB spatial queries the same file in place, see [AGENTS.md](./AGENTS.md) for those patterns. Paths are relative to this directory, and the same code works against the published URL.

## Schema, the Columns That Matter

Twenty-two of the 171 columns do most of the work.

| Column | Type | Description |
|---|---|---|
| `SOVEREIGNT` | varchar | The owning sovereign state, which differs from ADMIN for territories such as Greenland (Denmark). |
| `TYPE` | varchar | Unit type, Sovereign country, Country, Dependency, Disputed, Indeterminate, or Sovereignty. |
| `ADM0_A3` | varchar | Natural Earth's own three-letter country code. Never a sentinel value, and the join key to the populated places Collection. |
| `NAME` | varchar | Short map label, for example Dem. Rep. Congo. |
| `NAME_LONG` | varchar | Long-form name, for example Democratic Republic of the Congo. Differs from NAME on 21 rows. |
| `POP_EST` | double | Population estimate, mostly the 2019 vintage. See POP_YEAR. |
| `POP_YEAR` | integer | Year the population estimate refers to. |
| `GDP_MD` | integer | GDP in millions of US dollars, mostly the 2019 vintage. See GDP_YEAR. |
| `GDP_YEAR` | integer | Year the GDP figure refers to. |
| `ISO_A2` | varchar | ISO 3166-1 alpha-2 code, -99 for the same five countries as ISO_A3. |
| `ISO_A2_EH` | varchar | ISO alpha-2 with France, Norway, and Kosovo (XK) repaired. |
| `ISO_A3` | varchar | ISO 3166-1 alpha-3 code, with the sentinel -99 for France, Norway, Kosovo, Northern Cyprus, and Somaliland. Prefer ISO_A3_EH. |
| `ISO_A3_EH` | varchar | ISO alpha-3 with France and Norway repaired. The column to join external ISO-coded statistics on. |
| `CONTINENT` | varchar | Continent rollup. Includes the value Seven seas (open ocean), so a GROUP BY returns eight groups. |
| `REGION_UN` | varchar | United Nations macro region. |
| `SUBREGION` | varchar | United Nations subregion. |
| `LABEL_X` | double | Longitude of the preferred label point. |
| `LABEL_Y` | double | Latitude of the preferred label point. |
| `NE_ID` | bigint | Stable Natural Earth feature id, unique in this file. |
| `WIKIDATAID` | varchar | Wikidata QID, present on all 177 rows. |
| `geom` | geometry | Country geometry, polygon or multipolygon, WGS84 longitude and latitude. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Per-feature bounding box struct, the GeoParquet covering used for spatial predicate pushdown. |

The table has 171 columns in all. The full list with types lives in `table:columns` on the `data` asset.

## Join Statistics to Geometry

The reason this Collection is in the catalog. Any table keyed by ISO
country code joins here for mapping, like the Eurostat electricity
prices table two directories over. Join on `ISO_A2_EH` or `ISO_A3_EH`,
not the raw ISO columns, which hold -99 for France and Norway.

```sql
INSTALL spatial; LOAD spatial;
SELECT n.NAME, e.OBS_VALUE AS eur_per_kwh, n.geom
FROM read_parquet('../../tabular/eurostat-electricity-prices/eurostat-electricity-prices.parquet') e
JOIN read_parquet('natural-earth-countries.parquet') n
  ON (CASE e.geo WHEN 'EL' THEN 'GR' WHEN 'UK' THEN 'GB' ELSE e.geo END) = n.ISO_A2_EH
WHERE e.TIME_PERIOD = '2025-S2' AND e.nrg_cons = 'KWH2500-4999'
  AND e.tax = 'I_TAX' AND e.currency = 'EUR';
```

## Suggested Uses

Choropleths of ISO-coded statistics, continent and region rollups, and
quick spatial-query demos. The `MAPCOLOR7` through `MAPCOLOR13` columns
assign map colors so neighboring countries differ, and `LABEL_X` and
`LABEL_Y` carry hand-placed label points, both there for basemap
rendering.

## Limitations

Not authoritative for legal boundaries. Natural Earth draws de facto
control, so Crimea, Kashmir, and Western Sahara follow the situation on
the ground, not treaties. Not measurement geometry either. At 1:110m a
coastline is simplified by tens of kilometres, and 43 small countries
and territories, from Andorra and Malta to Singapore and the Vatican,
have no polygon at all. Population and GDP are 2019 estimates. Upstream
publishes no formal accuracy figures, and the last cultural release was
in May 2022.

## Provenance and License

License, CC0-1.0.
Providers, Natural Earth (producer, licensor), Portolan SDI (host).
Original source, https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip .
Features, 177. Cloud-native asset, natural-earth-countries.parquet (GeoParquet 2.0).
