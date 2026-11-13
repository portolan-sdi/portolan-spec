# Natural Earth Populated Places (1:50m)

Point locations of populated places, cities and towns, at 1:50m scale from Natural Earth. Public domain reference points, republished as cloud-native GeoParquet alongside the original zipped Shapefile.

City and town points at 1:50m scale from
[Natural Earth](https://www.naturalearthdata.com), version 5.1.2 from
May 2022. The 1,251 points cover every national and most first-level
capitals, major cities, and, in Natural Earth's own words, a sampling
of smaller towns in sparsely inhabited regions, favoring regional
significance over population census. LandScan-derived population
estimates cover about 90 percent of the places.

Agents, read [AGENTS.md](./AGENTS.md) first, especially before joining
these points to country polygons.

## What Counts as a Place

The `FEATURECLA` column answers it. 482 Admin-1 capitals, 414 plain
populated places, 202 national capitals, and some surprises, 40
Antarctic research stations including Amundsen-Scott at exactly 90
degrees south, 13 alternate capitals such as The Hague and Lagos, and
one historic place, the abandoned Siberian port of Ambarchik with
population zero. Filter on it before counting cities.

## Quick Start

```python
import geopandas as gpd

gdf = gpd.read_parquet("natural-earth-populated-places.parquet")
print(gdf.head())
```

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column, so it needs a GeoPandas built on pyarrow 24 or newer. DuckDB spatial queries the same file in place, see [AGENTS.md](./AGENTS.md) for those patterns. Paths are relative to this directory, and the same code works against the published URL.

## Sizing and Filtering Labels

The cartographic columns are the point of this theme. Natural Earth's
guidance is to size labels from `POP_MAX` and thin them with the scale
rankings, and `MIN_ZOOM` maps that to web-map zoom levels directly.

```sql
SELECT NAME, POP_MAX, SCALERANK
FROM read_parquet('natural-earth-populated-places.parquet')
WHERE SCALERANK = 0
ORDER BY POP_MAX DESC LIMIT 5;
```

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
| `SCALERANK` | integer | Importance rank 0 to 10, 0 most important. Filter on it to thin labels by zoom. |
| `FEATURECLA` | varchar | What kind of place this is. Admin-0 capital, Admin-1 capital, Populated place, Scientific station, and four rarer classes. |
| `NAME` | varchar | Display name with diacritics, for example Neuquén. Not unique, several city names repeat across countries. |
| `NAMEPAR` | varchar | Other name in common use. Natural Earth sets it only when one such name exists. |
| `NAMEALT` | varchar | Alternate names as a list, where Natural Earth finds them appropriate. |
| `NAMEASCII` | varchar | ASCII fallback spelling of the name. |
| `ADM0CAP` | integer | 1 marks a national capital, 200 rows in this file. |
| `CAPIN` | varchar | Kind of capital, for example Administrative or De facto capita. Natural Earth sets it only for a country capital. The values are cut at 15 characters. |
| `WORLDCITY` | integer | 1 flags 70 globally prominent cities. |
| `MEGACITY` | integer | 1 flags the 462 places Natural Earth treats as megacities. |
| `SOV0NAME` | varchar | Name of the Natural Earth sovereign state that the point falls in. |
| `SOV_A3` | varchar | Code of the Natural Earth sovereign state that the point falls in. |
| `ADM0NAME` | varchar | Country name the point belongs to. |
| `ADM0_A3` | varchar | Natural Earth country code, the join key to the countries Collection. |
| `ADM1NAME` | varchar | First-level admin region the point belongs to. |
| `ISO_A2` | varchar | ISO alpha-2 code of the Natural Earth country that the point falls in. |
| `POP_MAX` | bigint | Population of the metro area, LandScan derived. Tokyo carries 35,676,000. |
| `POP_MIN` | bigint | Population of the city proper. Tokyo carries 8,336,599. |
| `RANK_MAX` | integer | Population rank from 0 to 14, calculated from POP_MAX with the formula that Natural Earth publishes. Rank 14 is more than 10 million people. |
| `RANK_MIN` | integer | Population rank from 0 to 14, calculated from POP_MIN with the formula that Natural Earth publishes. Rank 14 is more than 10 million people. |
| `TIMEZONE` | varchar | IANA time zone name, empty for 114 rows. |
| `MIN_ZOOM` | double | Suggested minimum web-map zoom for showing the place. |
| `WIKIDATAID` | varchar | Wikidata QID, missing for 7 rows. |
| `WOF_ID` | bigint | Who's On First id of the place, where one is available. |
| `NAME_EN` | varchar | Name in English. Natural Earth takes its localized names from Wikidata. |
| `NAME_DE` | varchar | Name in German. Natural Earth takes its localized names from Wikidata. |
| `NAME_ES` | varchar | Name in Spanish. Natural Earth takes its localized names from Wikidata. |
| `NAME_FR` | varchar | Name in French. Natural Earth takes its localized names from Wikidata. |
| `NAME_PT` | varchar | Name in Portuguese. Natural Earth takes its localized names from Wikidata. |
| `NAME_RU` | varchar | Name in Russian. Natural Earth takes its localized names from Wikidata. |
| `NAME_ZH` | varchar | Name in Simplified Chinese. Natural Earth takes its localized names from Wikidata. |
| `NAME_AR` | varchar | Name in Arabic. Natural Earth takes its localized names from Wikidata. |
| `NAME_BN` | varchar | Name in Bengali. Natural Earth takes its localized names from Wikidata. |
| `NAME_EL` | varchar | Name in Greek. Natural Earth takes its localized names from Wikidata. |
| `NAME_HI` | varchar | Name in Hindi. Natural Earth takes its localized names from Wikidata. |
| `NAME_HU` | varchar | Name in Hungarian. Natural Earth takes its localized names from Wikidata. |
| `NAME_ID` | varchar | Name in Indonesian. Natural Earth takes its localized names from Wikidata. |
| `NAME_IT` | varchar | Name in Italian. Natural Earth takes its localized names from Wikidata. |
| `NAME_JA` | varchar | Name in Japanese. Natural Earth takes its localized names from Wikidata. |
| `NAME_KO` | varchar | Name in Korean. Natural Earth takes its localized names from Wikidata. |
| `NAME_NL` | varchar | Name in Dutch. Natural Earth takes its localized names from Wikidata. |
| `NAME_PL` | varchar | Name in Polish. Natural Earth takes its localized names from Wikidata. |
| `NAME_SV` | varchar | Name in Swedish. Natural Earth takes its localized names from Wikidata. |
| `NAME_TR` | varchar | Name in Turkish. Natural Earth takes its localized names from Wikidata. |
| `NAME_VI` | varchar | Name in Vietnamese. Natural Earth takes its localized names from Wikidata. |
| `NE_ID` | bigint | Stable Natural Earth feature id, unique in this file. |
| `NAME_FA` | varchar | Name in Farsi. Natural Earth takes its localized names from Wikidata. |
| `NAME_HE` | varchar | Name in Hebrew. Natural Earth takes its localized names from Wikidata. |
| `NAME_UK` | varchar | Name in Ukrainian. Natural Earth takes its localized names from Wikidata. |
| `NAME_UR` | varchar | Name in Urdu. Natural Earth takes its localized names from Wikidata. |
| `NAME_ZHT` | varchar | Name in Traditional Chinese. Natural Earth takes its localized names from Wikidata. |
| `GEONAMESID` | bigint | GeoNames id, missing for 43 rows. |
| `FCLASS_ISO` | varchar | Feature class from the ISO point of view. Null where that point of view sets no class. |
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
| `FCLASS_TLC` | varchar | Feature class from the top-level-country (TLC) point of view. Null where that point of view sets no class. |
| `geom` | geometry | Point geometry, WGS84 longitude and latitude. Use it instead of the legacy LATITUDE and LONGITUDE columns. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Per-feature bounding box struct, the GeoParquet covering. |

The table has 140 columns in all. The full list with types lives in `table:columns` on the collection.

## Limitations

A curated cartographic layer, not a gazetteer and not a demographic
dataset. Absence means Natural Earth chose not to include a town, not
that it does not exist, and the population figures are 2019-era
estimates for label sizing, not census data. `POP_MAX` counts the
metro area and `POP_MIN` the city proper, so ranking cities without
picking one deliberately mixes definitions. Names repeat, Mérida,
Portland, and Valencia each appear twice, so use `NE_ID` as the key.

## Provenance and License

License, CC0-1.0.
Providers, Natural Earth (producer, licensor), Portolan SDI (host).
Original source, https://naciscdn.org/naturalearth/50m/cultural/ne_50m_populated_places.zip .
Features, 1,251. Cloud-native asset, natural-earth-populated-places.parquet (GeoParquet 2.0).
