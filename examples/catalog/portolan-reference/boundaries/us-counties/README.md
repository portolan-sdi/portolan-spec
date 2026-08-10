# United States Counties (2023, 1:500k)

County and equivalent boundaries for the United States, the 2023 cartographic boundary file at 1:500,000 from the US Census Bureau, generalized for small-scale mapping. Republished as cloud-native GeoParquet alongside the original zipped Shapefile.

Every county and county equivalent in the United States and its
territories, 3,235 polygons as of January 1, 2023, from the
[US Census Bureau's cartographic boundary files](https://www.census.gov/geographies/mapping-files/time-series/geo/cartographic-boundary.html).
Cartographic boundary files are generalized from the authoritative
[TIGER/Line](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html)
database for thematic mapping, simplified to 1:500,000 and clipped to
the shoreline, so coastal counties look like the coastline rather than
extending into their legal water area. A new vintage ships every year.

The `GEOID` column is the five-digit county FIPS code that keys county
statistics across the US government, Census ACS and decennial tables,
BLS employment, CDC health data, USDA agriculture. That join is what
this Collection is for.

Agents, [AGENTS.md](./AGENTS.md) carries the FIPS join hazards, the
area-calculation trap, and tested queries.

## Quick Start

```python
import geopandas as gpd

gdf = gpd.read_parquet("us-counties.parquet")
print(gdf.head())
```

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column, so it needs a GeoPandas built on pyarrow 24 or newer. DuckDB spatial queries the same file in place, see [AGENTS.md](./AGENTS.md) for those patterns. Paths are relative to this directory, and the same code works against the published URL.

## Not Every County Is a County

The file holds 3,144 county equivalents in the 50 states and DC plus 91
in the territories, and the `LSAD` column tells them apart, 2,999
counties, 78 Puerto Rico municipios, 64 Louisiana parishes, 40
independent cities, Alaska's boroughs and census areas, and more.
Connecticut is the one to know about. In June 2022 the Census Bureau
[replaced its eight legacy counties](https://www.federalregister.gov/documents/2022/06/06/2022-12063/change-to-county-equivalents-in-the-state-of-connecticut)
with nine planning regions, so this file carries GEOIDs 09110 through
09190 and any dataset still keyed to 09001 through 09015 will not join.

## Schema

| Column | Type | Description |
|---|---|---|
| `STATEFP` | varchar | Two-digit state or territory FIPS code as a zero-padded string. |
| `COUNTYFP` | varchar | Three-digit county FIPS code, unique within its state. |
| `COUNTYNS` | varchar | Eight-digit ANSI (GNIS) code, the permanent identifier that survives FIPS reassignment. |
| `GEOIDFQ` | varchar | Fully qualified GEOID, 0500000US plus GEOID. Matches the GEO_ID column in data.census.gov downloads directly. Called AFFGEOID before the 2023 vintage. |
| `GEOID` | varchar | Five-digit STATEFP plus COUNTYFP concatenation, the standard join key for US county statistics. Keep it a string, integer casts strip the leading zero. |
| `NAME` | varchar | Base name only, for example Denver. 31 rows are named Washington, so never key on it. |
| `NAMELSAD` | varchar | Name with its legal or statistical description, for example St. Louis city. The display name. |
| `STUSPS` | varchar | Two-letter USPS state or territory abbreviation. |
| `STATE_NAME` | varchar | Full state or territory name. |
| `LSAD` | varchar | Legal or statistical area description code. Twelve kinds of county equivalent appear in this file. |
| `ALAND` | bigint | Land area in square meters, computed from the full-resolution legal boundary, not from this generalized geometry. |
| `AWATER` | bigint | Water area in square meters, including territorial water that lies outside the clipped shoreline geometry. |
| `geom` | geometry('epsg:4269') | County geometry clipped to the shoreline, NAD83 longitude and latitude. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Per-feature bounding box struct, the GeoParquet covering. |

The table has 15 columns in all. The full list with types lives in `table:columns` on the `data` asset.

## Join Census Data

`GEOIDFQ` equals the GEO_ID column of every table downloaded from
[data.census.gov](https://data.census.gov), so American Community
Survey data joins with no string surgery. The pattern, with the ACS
table read from a downloaded CSV.

```
SELECT c.NAMELSAD, acs.estimate
FROM 'us-counties.parquet' c
JOIN 'acs_table.csv' acs ON acs.GEO_ID = c.GEOIDFQ
```

## Suggested Uses

County choropleths of any FIPS-keyed statistic, the same role the
Census files play behind the D3 ecosystem's
[us-atlas](https://github.com/topojson/us-atlas), state-level rollups
via `STATEFP`, and point-in-county lookups at city scale and coarser.

## Limitations

The Census Bureau's own guidance rules out geographic analysis
including area or perimeter calculation, geocoding, and legal boundary
determination. Use `ALAND` and `AWATER` for areas, they come from the
full-resolution geography. At neighborhood zoom the generalized lines
visibly cut corners, and small offshore islands may be missing
entirely. Boundaries are the January 1, 2023 vintage, so data keyed to
other years can mismatch, Connecticut above all.

## Provenance and License

License, CC0-1.0.
Providers, U.S. Census Bureau (producer, licensor), Portolan SDI (host).
Original source, https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip .
Features, 3,235. Cloud-native asset, us-counties.parquet (GeoParquet 2.0).
