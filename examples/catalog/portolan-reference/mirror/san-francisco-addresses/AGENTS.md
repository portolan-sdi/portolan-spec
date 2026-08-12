# Agent Guidance, San Francisco Addresses (EAS)

A fixed 5,000-row extract of a 388,550-row live address layer. Two
rules prevent most wrong answers. Never extrapolate counts or
densities from this sample to San Francisco. Never count rows when
you mean addresses, one row is a base address, a unit, and a parcel
link, so `count(*)` is 5,000 while distinct buildings are 4,488.

Query the GeoParquet `data` asset in place with DuckDB spatial, read_parquet('san-francisco-addresses.parquet'), or load it with GeoPandas. It streams over HTTP range requests, so query the published URL directly rather than downloading first. For rendering use the visual PMTiles asset with its MapLibre styles.

## Quirks

- 327 Fulton St appears 18 times, identical address, 18 condo parcel
  links. Count buildings with count(DISTINCT eas_baseid) and
  addresses with count(DISTINCT eas_subid).
- Units carry their building's single point, every eas_baseid has
  exactly one distinct geometry. Deduplicate by base before density
  maps or clustering.
- parcel_number is null on 1,596 rows, mostly records sourced from
  the State of CA, so a parcel join silently drops a third of the
  extract.
- data_updated_at holds the epoch sentinel 1970-01-01 on 2,378 rows,
  meaning never updated, not 1970. Filter before temporal analysis.
- Nearly every column is text, including latitude, longitude,
  supervisor, and zip_code. Cast before arithmetic, and read
  coordinates from geom instead.
- numbertext spells out the supervisor district, not the address
  number, and supname holds the 2026 incumbents, which dates the
  snapshot.

## Coordinate Reference System

EPSG:4326, WGS 84, a geographic coordinate reference system whose coordinates are in degrees.
Planar distance functions return degrees, which are not ground units and vary with latitude. For real distances use a sphere or spheroid function, or transform to a projected CRS first.
The `data` asset carries the same code as `proj:code`.

For metric distances use `ST_Distance_Sphere` with
`geometry_always_xy` set, as the query below does, or transform to
EPSG:26910, UTM zone 10N, for planar work over San Francisco.

## Tested Queries

The grain, records against buildings against units.

```sql
SELECT count(*) AS record_count,
       count(DISTINCT eas_baseid) AS buildings,
       count(*) FILTER (unit_number IS NOT NULL) AS unit_records
FROM read_parquet('san-francisco-addresses.parquet');
-- 5000, 4488, 2060.
```

Addresses within 250 meters of a point, metric distance done right.

```sql
INSTALL spatial; LOAD spatial;
SET geometry_always_xy = true;
SELECT address,
       round(ST_Distance_Sphere(geom, ST_Point(-122.419331, 37.779237))) AS meters
FROM read_parquet('san-francisco-addresses.parquet')
WHERE ST_Distance_Sphere(geom, ST_Point(-122.419331, 37.779237)) < 250
ORDER BY meters LIMIT 5;
-- One row, 512 Van Ness Ave #415 at 136 meters.
```

Buildings with the most sampled units.

```sql
SELECT any_value(address_number) AS num,
       any_value(street_full_street_name) AS street,
       count(DISTINCT unit_number) AS units
FROM read_parquet('san-francisco-addresses.parquet')
WHERE unit_number IS NOT NULL
GROUP BY eas_baseid ORDER BY units DESC LIMIT 3;
-- 1000 Pine St with 17 sampled units, 601 Van Ness Ave with 11.
```

## Related Collections

Nothing joins inside this catalog, the EAS keys point outward.
parcel_number joins DataSF's Parcels layer on blklot, cnn joins the
street centerlines, nhood joins Analysis Neighborhoods by name. The
upstream is a live Socrata endpoint, referenced by URL only. This
extract was converted to GeoParquet 2.0 with DuckDB spatial and dates
itself, every row carries data_as_of July 24, 2026.
