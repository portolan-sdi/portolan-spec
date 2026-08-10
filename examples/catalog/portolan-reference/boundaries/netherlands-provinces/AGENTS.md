# Agent Guidance, Netherlands Provinces

Dutch province polygons whose `identificatie` codes PV20 to PV31 join
CBS StatLine, the same code system all Dutch government data uses at
province level. The `code` column, bare 20 to 31, joins the
municipality layer of the same upstream GeoPackage on
ligt_in_provincie_code.

Query the GeoParquet `data` asset in place with DuckDB spatial, read_parquet('netherlands-provinces.parquet'), or load it with GeoPandas. It streams over HTTP range requests, so query the published URL directly rather than downloading first. For rendering use the visual PMTiles asset with its MapLibre styles.

## CRS, a Metric National Grid

EPSG:28992, Amersfoort / RD New, the Dutch national grid in meters,
valid only for the European Netherlands. `ST_Area(geom)` returns
square meters directly, divide by 1e6 for square kilometres, and the
results match CBS official figures to one decimal. Web maps need
`ST_Transform(geom, 'EPSG:28992', 'EPSG:4326', always_xy := true)`,
and without always_xy the axes come back flipped. Points must be
transformed into RD before ST_Contains. The bbox covering column is
also in RD meters, while the STAC extent in collection.json is WGS84.

## Quirks

- Fryslân, not Friesland. The naam column uses official spellings with
  diacritics.
- Noord-Brabant is a 9-part multipolygon with 22 holes, the Baarle
  enclave complex on the Belgian border. Belgian exclaves are punched
  out and 8 tiny Dutch counter-enclaves float inside them, so
  one-province-one-polygon assumptions and small-area filters both
  break.
- Provinces include their water. Fryslân is the largest by total area
  and third by land.
- CBS OData v3 keys carry trailing spaces, PV20 with two spaces. Trim
  before joining.
- fid order is arbitrary, Flevoland is 1 and Groningen is 11. Key on
  code or identificatie.

## Tested Queries

Areas that reproduce official statistics.

```sql
INSTALL spatial; LOAD spatial;
SELECT naam, code, round(ST_Area(geom) / 1e6, 1) AS area_km2
FROM read_parquet('netherlands-provinces.parquet')
ORDER BY area_km2 DESC LIMIT 3;
-- Fryslân 5753.3, Gelderland 5136.3, Noord-Brabant 5082.1.
```

Which province contains a point, in RD meters. Amsterdam.

```sql
INSTALL spatial; LOAD spatial;
SELECT naam FROM read_parquet('netherlands-provinces.parquet')
WHERE ST_Contains(geom, ST_Point(121687, 487484));
-- Noord-Holland.
```

The Baarle enclave forensic, parts of Noord-Brabant.

```sql
INSTALL spatial; LOAD spatial;
WITH parts AS (
  SELECT unnest(ST_Dump(geom)) AS d
  FROM read_parquet('netherlands-provinces.parquet')
  WHERE naam = 'Noord-Brabant')
SELECT count(*) AS parts, round(min(ST_Area(d.geom)) / 1e6, 4) AS smallest_km2
FROM parts;
-- 9 parts, the smallest 0.0029 km2. DuckDB has no ST_GeometryN, use unnest.
```

## Related Collections

The upstream GeoPackage also carries the 342 municipalities
(gemeentegebied) and the national outline (landgebied), joined on the
code columns above. Within this catalog the other boundary Collections
connect only spatially. Converted from PDOK's GeoPackage with DuckDB
spatial into web-optimized GeoParquet 2.0, preserving the source CRS.
The mirrored ISO 19115 record is the metadata asset beside the data.
