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

## Schema

Natural Earth publishes no data dictionary, and its maintainer
[declined to write one](https://github.com/nvkelso/natural-earth-vector/issues/153).
The table lists every column that has a description. A description
comes from the Natural Earth release notes, changelog, or maintainer,
or from values that this file shows. The other columns have no
description because the source defines none. They are in
`table:columns` with a name and a type only.

| Column | Type | Description |
|---|---|---|
| `fid` | bigint | Feature id that GDAL assigned when the generator read the source layer. Unique in this file. It is not an upstream key. |
| `SOVEREIGNT` | varchar | The owning sovereign state, which differs from ADMIN for territories such as Greenland (Denmark). |
| `SOV_A3` | varchar | Natural Earth three-letter code of the sovereign state. Natural Earth states that the code is unique to its own coding system and somewhat follows the ISO alpha-3 codes. |
| `TYPE` | varchar | Unit type, Sovereign country, Country, Dependency, Disputed, Indeterminate, or Sovereignty. |
| `TLC` | varchar | Flag for the top-level-country (TLC) point of view. Natural Earth describes TLC as a superset of ISO. The value is 1 in 176 rows and null in one row. |
| `ADM0_A3` | varchar | Natural Earth's own three-letter country code. Never a sentinel value, and the join key to the populated places Collection. |
| `GEOU_DIF` | integer | Flag that states if the geographic unit is different from its parent administrative unit. Natural Earth provides it so that a map does not repeat labels. The value is 0 in every row of this file. |
| `GU_A3` | varchar | Natural Earth three-letter code of the geographic unit. Natural Earth states that the code is unique to its own coding system and somewhat follows the ISO alpha-3 codes. |
| `SU_A3` | varchar | Natural Earth three-letter code of the administrative sub-unit. Natural Earth states that it is like an ISO alpha-3 code, but different. |
| `NAME` | varchar | Short map label, for example Dem. Rep. Congo. |
| `NAME_LONG` | varchar | Long-form name, for example Democratic Republic of the Congo. Differs from NAME on 21 rows. |
| `NOTE_ADM0` | varchar | Short note that gives context to the sovereignty of the feature, such as Fr. or U.K. Null for most rows. |
| `NOTE_BRK` | varchar | Note that gives context to the sovereignty of a breakaway or disputed feature, such as Self admin.; Claimed by Cyprus. Null for most rows. |
| `NAME_SORT` | varchar | Name for sorted lists. Natural Earth provides it so that a list can ignore a prefix such as The. |
| `MAPCOLOR7` | integer | Map color index. Natural Earth states that its map color derives from a US State Department political world map, where no neighboring countries have the same color and all territories of a sovereign state share one color. |
| `MAPCOLOR8` | integer | Map color index. Natural Earth states that its map color derives from a US State Department political world map, where no neighboring countries have the same color and all territories of a sovereign state share one color. |
| `MAPCOLOR9` | integer | Map color index. Natural Earth states that its map color derives from a US State Department political world map, where no neighboring countries have the same color and all territories of a sovereign state share one color. |
| `MAPCOLOR13` | integer | Map color index. Natural Earth states that its map color derives from a US State Department political world map, where no neighboring countries have the same color and all territories of a sovereign state share one color. |
| `POP_EST` | double | Population estimate, mostly the 2019 vintage. See POP_YEAR. |
| `POP_YEAR` | integer | Year the population estimate refers to. |
| `GDP_MD` | integer | GDP in millions of US dollars, mostly the 2019 vintage. See GDP_YEAR. |
| `GDP_YEAR` | integer | Year the GDP figure refers to. |
| `ISO_A2` | varchar | ISO 3166-1 alpha-2 code, -99 for the same five countries as ISO_A3. |
| `ISO_A2_EH` | varchar | ISO alpha-2 with France, Norway, and Kosovo (XK) repaired. |
| `ISO_A3` | varchar | ISO 3166-1 alpha-3 code, with the sentinel -99 for France, Norway, Kosovo, Northern Cyprus, and Somaliland. Prefer ISO_A3_EH. |
| `ISO_A3_EH` | varchar | ISO alpha-3 with France and Norway repaired. The column to join external ISO-coded statistics on. |
| `ADM0_ISO` | varchar | Country code in the ISO point of view. Natural Earth renamed it from adm0_a3_iso in version 5.1.0. |
| `ADM0_TLC` | varchar | Country code in the top-level-country (TLC) point of view, which Natural Earth added in version 5.1.0. |
| `CONTINENT` | varchar | Continent rollup. Includes the value Seven seas (open ocean), so a GROUP BY returns eight groups. |
| `REGION_UN` | varchar | United Nations macro region. |
| `SUBREGION` | varchar | United Nations subregion. |
| `MIN_ZOOM` | double | Minimum web map zoom at which to show the feature. Natural Earth optimizes it for the web Mercator projection. |
| `MIN_LABEL` | double | Minimum zoom at which to show the label. Natural Earth provides it where the label appears later than the geometry. |
| `MAX_LABEL` | double | Zoom at which the label stops. |
| `LABEL_X` | double | Longitude of the preferred label point. |
| `LABEL_Y` | double | Latitude of the preferred label point. |
| `NE_ID` | bigint | Stable Natural Earth feature id, unique in this file. |
| `WIKIDATAID` | varchar | Wikidata QID, present on all 177 rows. |
| `NAME_AR` | varchar | Name in Arabic. Natural Earth takes its localized names from Wikidata. |
| `NAME_BN` | varchar | Name in Bengali. Natural Earth takes its localized names from Wikidata. |
| `NAME_DE` | varchar | Name in German. Natural Earth takes its localized names from Wikidata. |
| `NAME_EN` | varchar | Name in English. Natural Earth takes its localized names from Wikidata. |
| `NAME_ES` | varchar | Name in Spanish. Natural Earth takes its localized names from Wikidata. |
| `NAME_FA` | varchar | Name in Farsi. Natural Earth takes its localized names from Wikidata. |
| `NAME_FR` | varchar | Name in French. Natural Earth takes its localized names from Wikidata. |
| `NAME_EL` | varchar | Name in Greek. Natural Earth takes its localized names from Wikidata. |
| `NAME_HE` | varchar | Name in Hebrew. Natural Earth takes its localized names from Wikidata. |
| `NAME_HI` | varchar | Name in Hindi. Natural Earth takes its localized names from Wikidata. |
| `NAME_HU` | varchar | Name in Hungarian. Natural Earth takes its localized names from Wikidata. |
| `NAME_ID` | varchar | Name in Indonesian. Natural Earth takes its localized names from Wikidata. |
| `NAME_IT` | varchar | Name in Italian. Natural Earth takes its localized names from Wikidata. |
| `NAME_JA` | varchar | Name in Japanese. Natural Earth takes its localized names from Wikidata. |
| `NAME_KO` | varchar | Name in Korean. Natural Earth takes its localized names from Wikidata. |
| `NAME_NL` | varchar | Name in Dutch. Natural Earth takes its localized names from Wikidata. |
| `NAME_PL` | varchar | Name in Polish. Natural Earth takes its localized names from Wikidata. |
| `NAME_PT` | varchar | Name in Portuguese. Natural Earth takes its localized names from Wikidata. |
| `NAME_RU` | varchar | Name in Russian. Natural Earth takes its localized names from Wikidata. |
| `NAME_SV` | varchar | Name in Swedish. Natural Earth takes its localized names from Wikidata. |
| `NAME_TR` | varchar | Name in Turkish. Natural Earth takes its localized names from Wikidata. |
| `NAME_UK` | varchar | Name in Ukrainian. Natural Earth takes its localized names from Wikidata. |
| `NAME_UR` | varchar | Name in Urdu. Natural Earth takes its localized names from Wikidata. |
| `NAME_VI` | varchar | Name in Vietnamese. Natural Earth takes its localized names from Wikidata. |
| `NAME_ZH` | varchar | Name in Simplified Chinese. Natural Earth takes its localized names from Wikidata. |
| `NAME_ZHT` | varchar | Name in Traditional Chinese. Natural Earth takes its localized names from Wikidata. |
| `FCLASS_ISO` | varchar | Feature class from the ISO point of view. Natural Earth lists the values Admin-0 country, Admin-0 dependency, Admin-1 states provinces, and Unrecognized. |
| `TLC_DIFF` | varchar | Flag that Natural Earth added with the top-level-country (TLC) point of view. The value is 1 in 4 rows and null in the others. |
| `FCLASS_TLC` | varchar | Feature class from the top-level-country (TLC) point of view. This file contains Admin-0 country, Admin-0 dependency, and Unrecognized. |
| `FCLASS_US` | varchar | Feature class from the point of view of the United States. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_FR` | varchar | Feature class from the point of view of France. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_RU` | varchar | Feature class from the point of view of Russia. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_ES` | varchar | Feature class from the point of view of Spain. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_CN` | varchar | Feature class from the point of view of China. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_TW` | varchar | Feature class from the point of view of Taiwan. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_IN` | varchar | Feature class from the point of view of India. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_NP` | varchar | Feature class from the point of view of Nepal. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_PK` | varchar | Feature class from the point of view of Pakistan. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_DE` | varchar | Feature class from the point of view of Germany. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_GB` | varchar | Feature class from the point of view of the United Kingdom. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_BR` | varchar | Feature class from the point of view of Brazil. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_IL` | varchar | Feature class from the point of view of Israel. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_PS` | varchar | Feature class from the point of view of Palestine. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_SA` | varchar | Feature class from the point of view of Saudi Arabia. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_EG` | varchar | Feature class from the point of view of Egypt. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_MA` | varchar | Feature class from the point of view of Morocco. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_PT` | varchar | Feature class from the point of view of Portugal. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_AR` | varchar | Feature class from the point of view of Argentina. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_JP` | varchar | Feature class from the point of view of Japan. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_KO` | varchar | Feature class from the point of view of South Korea. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_VN` | varchar | Feature class from the point of view of Vietnam. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_TR` | varchar | Feature class from the point of view of Turkey. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_ID` | varchar | Feature class from the point of view of Indonesia. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_PL` | varchar | Feature class from the point of view of Poland. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_GR` | varchar | Feature class from the point of view of Greece. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_IT` | varchar | Feature class from the point of view of Italy. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_NL` | varchar | Feature class from the point of view of the Netherlands. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_SE` | varchar | Feature class from the point of view of Sweden. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_BD` | varchar | Feature class from the point of view of Bangladesh. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `FCLASS_UA` | varchar | Feature class from the point of view of Ukraine. One of the Natural Earth FCLASS columns for alternate points of view. Null where that point of view sets no class. |
| `geom` | geometry | Country geometry, polygon or multipolygon, WGS84 longitude and latitude. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Per-feature bounding box struct, the GeoParquet covering used for spatial predicate pushdown. |

The table has 171 columns in all. The full list with types lives in `table:columns` on the collection.

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
