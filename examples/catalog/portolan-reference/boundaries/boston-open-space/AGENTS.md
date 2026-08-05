# Agent Guidance, Boston Open Space

Boston's official open space inventory, valuable and messy in the way
municipal GIS data actually is. No stable key, free-text code columns,
and sentinel strings. The quirks below are each verified against the
data and each prevents a silently wrong answer.

Query the GeoParquet `data` asset in place with DuckDB spatial, read_parquet('boston-open-space.parquet'), or load it with GeoPandas. It streams over HTTP range requests, so query the published URL directly rather than downloading first. For rendering use the visual PMTiles asset with its MapLibre styles.

## Quirks

- PROTECTION is a slash-separated free-text list with typos, Ch91 and
  Ch 91, CATMit and CAT Mit. Match with LIKE '%A97%', never equality.
  453 sites match A97, Article 97 constitutional protection.
- Null OS_Mngmnt means the steward in OS_Own_Jur manages the site
  itself. It is a meaningful value, not missing data.
- Sentinel strings pollute several columns, None, NULL, n/a, and angle
  bracket Null variants in OS_Own_Jur and AgncyJuris, plus one
  lowercase South end in DISTRICT.
- TypeLong has spelling variants, an and for ampersand form and a
  trailing-space form. Normalize with trim and replace before GROUP BY,
  and expect TYPECODE to contradict it on about 13 rows.
- Nine real sites carry ACRES = 0, so WHERE ACRES > 0 drops them. Fall
  back to geometry area for those.
- DISTRICT is the open space plan's districting, not official Boston
  neighborhoods, and four large linear parks are assigned the literal
  value Multi-District rather than a place.

## Area, Use the ACRES Column

Geometry is WGS84 degrees, so `ST_Area` returns square degrees. The
official `ACRES` column matches geodesic geometry area to a median of
0.003 acres, use it. If you must compute, DuckDB's spheroid function
wants latitude first, and skipping the flip shrinks Boston by more
than half.

```sql
INSTALL spatial; LOAD spatial;
SELECT round(sum(ST_Area_Spheroid(ST_FlipCoordinates(geom))) / 4046.8564) AS acres_flipped,
       round(sum(ACRES)) AS acres_official
FROM read_parquet('boston-open-space.parquet');
-- 7374 from geometry against 7356 official. Without the flip, 3250.
```

Eighteen sites disagree with their geometry by more than 10 percent,
documented cases like Condor Street Overlook where ACRES excludes
mudflats the polygon includes.

## Tested Queries

Acreage by normalized type.

```sql
SELECT trim(replace(TypeLong, ' and ', ' & ')) AS site_type,
       count(*) AS sites, round(sum(ACRES), 1) AS acres
FROM read_parquet('boston-open-space.parquet')
WHERE TypeLong IS NOT NULL
GROUP BY site_type ORDER BY acres DESC;
-- Six types, led by Parkways, Reservations & Beaches at 2,621.6 acres.
```

Which open space contains a point. Boston Common from its center.

```sql
INSTALL spatial; LOAD spatial;
SELECT SITE_NAME, DISTRICT, ACRES
FROM read_parquet('boston-open-space.parquet')
WHERE ST_Contains(geom, ST_Point(-71.0656, 42.3550));
-- Boston Common, Back Bay/Beacon Hill, 45.7 acres.
```

Protected share by district.

```sql
SELECT DISTRICT, round(sum(ACRES), 1) AS total_acres,
       round(sum(ACRES) FILTER (WHERE POS = 'X'), 1) AS protected_acres
FROM read_parquet('boston-open-space.parquet')
GROUP BY DISTRICT ORDER BY total_acres DESC LIMIT 3;
-- West Roxbury 1,215 total and 637 protected, then the Harbor Islands
-- and Roslindale.
```

## Related Collections

`boundaries/us-counties` contains Boston at a far coarser scale, and a
spatial join is the only bridge. The upstream layer on Analyze Boston
is continuously maintained and now carries columns this July 2026
snapshot predates, OS_ID, ZipCode, ParcelNumber, YearAcquired.
Converted from the city's Shapefile export with DuckDB spatial into
web-optimized GeoParquet 2.0.
