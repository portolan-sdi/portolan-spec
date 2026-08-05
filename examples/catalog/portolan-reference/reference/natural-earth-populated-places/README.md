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

## Schema, the Columns That Matter

Nineteen of the 140 columns cover most uses.

| Column | Type | Description |
|---|---|---|
| `SCALERANK` | integer | Importance rank 0 to 10, 0 most important. Filter on it to thin labels by zoom. |
| `FEATURECLA` | varchar | What kind of place this is. Admin-0 capital, Admin-1 capital, Populated place, Scientific station, and four rarer classes. |
| `NAME` | varchar | Display name with diacritics, for example Neuquén. Not unique, several city names repeat across countries. |
| `NAMEASCII` | varchar | ASCII fallback spelling of the name. |
| `ADM0CAP` | integer | 1 marks a national capital, 200 rows in this file. |
| `WORLDCITY` | integer | 1 flags 70 globally prominent cities. |
| `MEGACITY` | integer | 1 flags the 462 places Natural Earth treats as megacities. |
| `ADM0NAME` | varchar | Country name the point belongs to. |
| `ADM0_A3` | varchar | Natural Earth country code, the join key to the countries Collection. |
| `ADM1NAME` | varchar | First-level admin region the point belongs to. |
| `POP_MAX` | bigint | Population of the metro area, LandScan derived. Tokyo carries 35,676,000. |
| `POP_MIN` | bigint | Population of the city proper. Tokyo carries 8,336,599. |
| `TIMEZONE` | varchar | IANA time zone name, empty for 114 rows. |
| `MIN_ZOOM` | double | Suggested minimum web-map zoom for showing the place. |
| `WIKIDATAID` | varchar | Wikidata QID, missing for 7 rows. |
| `NE_ID` | bigint | Stable Natural Earth feature id, unique in this file. |
| `GEONAMESID` | bigint | GeoNames id, missing for 43 rows. |
| `geom` | geometry | Point geometry, WGS84 longitude and latitude. Use it instead of the legacy LATITUDE and LONGITUDE columns. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Per-feature bounding box struct, the GeoParquet covering. |

The table has 140 columns in all. The full list with types lives in `table:columns` on the `data` asset.

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
