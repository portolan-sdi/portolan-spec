# Agent Guidance, Natural Earth Countries (1:110m)

World country polygons for joins and rollups, not for legal boundaries
or precise areas. The stable key is `ADM0_A3`. External statistics join
on `ISO_A3_EH` or `ISO_A2_EH`. The raw `ISO_A3` and `ISO_A2` columns
hold the sentinel -99 for France, Norway, Kosovo, Northern Cyprus, and
Somaliland, so a filter like ISO_A3 = 'FRA' matches nothing.

Query the GeoParquet `data` asset in place with DuckDB spatial, read_parquet('natural-earth-countries.parquet'), or load it with GeoPandas. It streams over HTTP range requests, so query the published URL directly rather than downloading first. For a quick preview use the thumbnail asset.

## Quirks

- -99 is the global no-data sentinel, in the ISO columns and in numeric
  columns like TINY and MAPCOLOR13. Check for it before trusting a value.
- France includes French Guiana as one row, so its bbox spans from
  South America to Europe and bbox filters on South America catch France.
- South Sudan is `SDS` here but `SSD` in the populated places file. An
  `ADM0_A3` join between the two layers drops it unless you remap.
- Antarctica is a country row with population 4,490, and the continent
  column also holds Seven seas (open ocean) for the French Southern and
  Antarctic Lands.
- Russia and Fiji cross the antimeridian, so their bboxes span the full
  longitude range and naive bbox-width logic breaks.

## Coordinate Reference System

EPSG:4326, WGS 84, a geographic coordinate reference system whose coordinates are in degrees.
Planar distance and area functions return degrees and square degrees, which are not ground units and vary with latitude. For real distances and areas use a sphere or spheroid function, or transform to a projected CRS first.
The `data` asset carries the same code as `proj:code`.

Coordinates are stored longitude first. `ST_Area(geom)` in square
degrees makes Greenland read nearly as large as Brazil. For real areas
use the spheroid function, and set `geometry_always_xy` first, because
DuckDB still reads the first coordinate as latitude by default.

```sql
INSTALL spatial; LOAD spatial;
SET geometry_always_xy = true;
SELECT NAME, round(ST_Area_Spheroid(geom) / 1e6) AS km2
FROM read_parquet('natural-earth-countries.parquet')
ORDER BY km2 DESC LIMIT 5;
-- Russia 17,018,507 then Antarctica, Canada, United States, China.
-- Without the setting, Brazil returns 5.2M km2 instead of 8.5M and 33
-- countries return NaN.
```

## Tested Queries

Population by continent.

```sql
SELECT CONTINENT, count(*) AS countries, sum(POP_EST)::BIGINT AS pop
FROM read_parquet('natural-earth-countries.parquet')
GROUP BY CONTINENT ORDER BY pop DESC;
-- Asia 4.55B across 47 rows, Africa 1.31B across 51, eight groups in all.
```

Which country contains a point.

```sql
INSTALL spatial; LOAD spatial;
SELECT NAME, ADM0_A3
FROM read_parquet('natural-earth-countries.parquet')
WHERE ST_Contains(geom, ST_Point(13.405, 52.52));
-- Germany, DEU. ST_Point takes longitude first.
```

## Related Collections

`reference/natural-earth-populated-places` joins on `ADM0_A3` with the
South Sudan remap above. `tabular/eurostat-electricity-prices` joins on
`ISO_A2_EH` after remapping Eurostat's EL and UK codes, the worked
example lives in that Collection's README. Converted from the upstream
zipped Shapefile with DuckDB spatial into web-optimized GeoParquet 2.0.
