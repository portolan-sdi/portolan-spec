# Agent Guidance, Natural Earth Populated Places (1:50m)

Curated world city points that join to the countries Collection on
`ADM0_A3`. Join by attribute, never spatially. 113 of the 1,251 points,
Istanbul, Montevideo, and Geneva among them, fall outside their own
country's generalized 1:110m polygon because coastal simplification
pushes them offshore.

Query the GeoParquet `data` asset in place with DuckDB spatial, read_parquet('natural-earth-populated-places.parquet'), or load it with GeoPandas. It streams over HTTP range requests, so query the published URL directly rather than downloading first. For a quick preview use the thumbnail asset.

## Quirks

- The United States capital is spelled with two spaces after the comma,
  so NAME = 'Washington, D.C.' matches nothing. Use LIKE 'Washington%'
  or ADM0CAP = 1 with ADM0_A3 = 'USA'.
- South Sudan is `SSD` here but `SDS` in the countries file. Remap one
  side before joining, or Juba, Malakal, and Wau drop out.
- The legacy LATITUDE and LONGITUDE columns diverge from the geometry
  by up to 0.22 degrees. They are old label anchors, read `geom`.
- The UN time series columns POP1950 through POP2050 are populated only
  for the 463 UN-tracked agglomerations, zero elsewhere, and POP2050 is
  a projection.
- 59 places carry POP_MAX below 1,000, mostly stations and outposts, so
  population filters silently drop real capitals of small territories.

## Coordinate Reference System

EPSG:4326, WGS 84, a geographic coordinate reference system whose coordinates are in degrees.
Planar distance and area functions return degrees and square degrees, which are not ground units and vary with latitude. For real distances and areas use a sphere or spheroid function, or transform to a projected CRS first.
The `data` asset carries the same code as `proj:code`, so this and the machine-readable metadata cannot disagree.

The same CRS as the countries Collection, so the two overlay and join
without a transform. Nearest-neighbour work wants
`ST_Distance_Sphere`, which the query below uses.

## Tested Queries

Capitals per continent, with the country join done correctly.

```sql
INSTALL spatial; LOAD spatial;
SELECT c.CONTINENT, count(*) AS capitals
FROM read_parquet('natural-earth-populated-places.parquet') p
JOIN read_parquet('../natural-earth-countries/natural-earth-countries.parquet') c
  ON (CASE p.ADM0_A3 WHEN 'SSD' THEN 'SDS' ELSE p.ADM0_A3 END) = c.ADM0_A3
WHERE p.ADM0CAP = 1
GROUP BY c.CONTINENT ORDER BY capitals DESC;
-- Africa 52, Asia 45, Europe 39, then the Americas and Oceania.
```

Nearest city to a point, distance in kilometres.

```sql
INSTALL spatial; LOAD spatial;
SELECT NAME, ADM0NAME,
       round(ST_Distance_Sphere(geom, ST_Point(-122.4783, 37.8199)) / 1000, 1) AS km
FROM read_parquet('natural-earth-populated-places.parquet')
ORDER BY km LIMIT 3;
-- San Francisco 9.0 km, San Jose 71.7 km, Sacramento 120.4 km.
```

## Related Collections

`reference/natural-earth-countries` is the polygon companion, same
producer and vintage family, joined on `ADM0_A3` with the South Sudan
remap. Converted from the upstream zipped Shapefile with DuckDB spatial
into web-optimized GeoParquet 2.0.
