# Agent Guidance, United States Counties (2023, 1:500k)

County polygons whose value is the `GEOID` column, the five-digit FIPS
key to US county statistics. Join ACS and decennial downloads on
`GEOIDFQ` instead, it matches their GEO_ID column verbatim. `COUNTYNS`
is the identifier that survives FIPS changes across years.

Query the GeoParquet `data` asset in place with DuckDB spatial, read_parquet('us-counties.parquet'), or load it with GeoPandas. It streams over HTTP range requests, so query the published URL directly rather than downloading first. For rendering use the visual PMTiles asset with its MapLibre styles.

## Quirks

- GEOID is a zero-padded string. Cast it to integer and Alabama's 01001
  becomes 1001, silently unjoining every state below FIPS 10. CSV
  round-trips are the usual culprit.
- NAME is wildly ambiguous, 31 Washingtons, and independent cities
  collide with the counties that share their name. Baltimore city is
  24510, Baltimore County is 24005. The lowercase word city in NAMELSAD
  is what marks an independent city.
- Connecticut has nine planning regions, GEOIDs 09110 to 09190, LSAD
  PL, since the 2022 change. Datasets keyed to the old 09001 to 09015
  match nothing here.
- Aleutians West Census Area crosses the antimeridian, so its stored
  bbox spans nearly all longitudes and it passes almost every naive
  bbox filter. Handle it before bbox-windowing the world.
- Geometry is clipped to shoreline but AWATER is not, so San
  Francisco's polygon covers 122 km2 while ALAND plus AWATER is 601
  km2. Offshore points in legal county water fall in no polygon.

## Areas, the Wrong Way and the Right Way

Coordinates are NAD83 degrees, EPSG:4269, so `ST_Area` returns square
degrees and DuckDB's `ST_Area_Spheroid` returns NaN or wrong values on
several of these multipolygons. Trust `ALAND` and `AWATER`, or
transform to an equal-area CRS.

```sql
INSTALL spatial; LOAD spatial;
SELECT NAMELSAD,
       round(ST_Area(ST_Transform(geom, 'EPSG:4269', 'EPSG:5070', always_xy := true)) / 1e6, 1) AS km2,
       round(ALAND / 1e6, 1) AS aland_km2
FROM read_parquet('us-counties.parquet') WHERE GEOID = '08031';
-- Denver County, 400.7 km2 from geometry, 396.5 km2 of official land.
```

For web mapping, treating the NAD83 coordinates as WGS84 shifts
nothing visible at this generalization level.

## Tested Queries

Counties per state.

```sql
SELECT STUSPS, count(*) AS n
FROM read_parquet('us-counties.parquet')
GROUP BY STUSPS ORDER BY n DESC LIMIT 5;
-- Texas 254, Georgia 159, Virginia 133, Kentucky 120, Missouri 115.
```

Which county contains a point, longitude first.

```sql
INSTALL spatial; LOAD spatial;
SELECT GEOID, NAMELSAD, STUSPS
FROM read_parquet('us-counties.parquet')
WHERE ST_Contains(geom, ST_Point(-104.9903, 39.7392));
-- 08031, Denver County, CO.
```

Cheap spatial windows from the bbox covering column.

```sql
SELECT count(*) FROM read_parquet('us-counties.parquet')
WHERE bbox.xmin > -109.06 AND bbox.xmax < -102.04
  AND bbox.ymin > 36.99 AND bbox.ymax < 41.01;
-- 62 of Colorado's 64 counties, two generalized bboxes nick the state line.
```

## Related Collections

No attribute join inside this catalog, the FIPS ecosystem lives
outside it. Spatial joins against `boundaries/boston-open-space` or the
Natural Earth layers work at matching scales. Converted from the
upstream zipped Shapefile with DuckDB spatial into web-optimized
GeoParquet 2.0.
