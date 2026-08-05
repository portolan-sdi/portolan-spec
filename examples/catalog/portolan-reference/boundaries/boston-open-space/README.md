# Boston Open Space

City of Boston open spaces and parks, playgrounds, athletic fields, conservation land, and cemeteries, 1,012 polygons from the City of Boston GIS open data platform. Official primary source, republished as cloud-native GeoParquet with a PMTiles visualization and MapLibre styles.

Every open space of conservation and recreation interest in Boston,
1,012 polygons and 7,356 acres, from Franklin Park's 392 acres down to
pocket gardens, maintained by the
[Boston Parks and Recreation Department](https://www.boston.gov/departments/parks-and-recreation)
and published on [Analyze Boston](https://data.boston.gov/dataset/open-space).
The layer's defining trait is in its official description, regardless
of ownership. City parks sit beside 214 privately owned sites, state
reservations, cemeteries, and 124 community gardens.

This inventory is the basis of the city's
[Open Space and Recreation Plan 2023-2029](https://www.boston.gov/departments/parks-and-recreation/updating-seven-year-open-space-plan),
which reports 7.1 acres of protected open space per 1,000 residents,
and every site in it triggers design review within 100 feet under
Boston's Municipal Ordinance 7-4.11.

Agents, [AGENTS.md](./AGENTS.md) documents the free-text traps in this
very real municipal data, read it before aggregating.

## What Is in It

Six site types by acreage. Parkways, reservations, and beaches, 82
sites and 2,622 acres. Parks, playgrounds, and athletic fields, 361
sites and 2,559 acres. Cemeteries and burying grounds, 38 and 1,013.
Urban wilds and natural areas, 144 and 929. Malls, squares, and
plazas, 261 and 199. Community gardens, 124 sites and 32 acres.

## Quick Start

```python
import geopandas as gpd

gdf = gpd.read_parquet("boston-open-space.parquet")
print(gdf.head())
```

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column, so it needs a GeoPandas built on pyarrow 24 or newer. DuckDB spatial queries the same file in place, see [AGENTS.md](./AGENTS.md) for those patterns. Paths are relative to this directory, and the same code works against the published URL.

## Schema

| Column | Type | Description |
|---|---|---|
| `SITE_NAME` | varchar | Best-known or official site name. Multi-parcel sites carry Roman numeral suffixes, Stony Brook Reservation I and II. |
| `OWNERSHIP` | varchar | Fee owner where known. City of Boston, Commonwealth of Massachusetts, private owners, and agency abbreviations like BRA and BNAN. |
| `PROTECTION` | varchar | Slash-separated legal protection instruments. A97 is Article 97 of the Massachusetts Constitution, the strongest. Free text, match with LIKE. |
| `TYPECODE` | integer | Numeric open space type 1 through 7. Disagrees with TypeLong on about 13 rows, treat TypeLong as closer to intent. |
| `DISTRICT` | varchar | Planning district per the city's open space plan, not the official neighborhood boundaries. Includes the non-spatial value Multi-District. |
| `ACRES` | double | Official area in acres of the open-space portion, the figure to use instead of computing geometry area. |
| `ADDRESS` | varchar | Street address if known, null for 589 rows. |
| `ZonAgg` | varchar | Aggregated zoning district, for example Open Space District. |
| `TypeLong` | varchar | Open space type as text, with minor spelling variants worth normalizing before grouping. |
| `OS_Own_Jur` | varchar | The entity holding the open-space rights. BPRD, DCR, the Boston Conservation Commission, or None. |
| `OS_Mngmnt` | varchar | Managing entity only when it differs from OS_Own_Jur. Null means the steward manages it, not missing data. |
| `POS` | varchar | Protected open space flag. X permanently protected, N not. |
| `PA` | varchar | Public access flag. X accessible, A by appointment, N no or unknown access. |
| `ALT_NAME` | varchar | Official, previous, or colloquial alternate names. |
| `AgncyJuris` | varchar | Agency of jurisdiction for government-owned unprotected sites. Sparsely populated by design. |
| `ShapeSTAre` | double | ArcGIS-computed area in square meters from the source State Plane geometry. |
| `ShapeSTLen` | double | ArcGIS-computed perimeter in meters. |
| `geom` | geometry | Site geometry, WGS84 longitude and latitude. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Per-feature bounding box struct, the GeoParquet covering. |

The table has 21 columns in all. The full list with types lives in `table:columns` on the `data` asset.

## Protection and Access Are Columns, Not Assumptions

Being in this file does not mean a site is a public park. Cross the
two flag columns before any access or equity claim. `POS` says whether
a site is permanently protected, 450 sites and 5,015 acres are, mostly
under Article 97 of the Massachusetts Constitution, which requires a
two-thirds vote of the legislature to convert conservation land.
`PA` says whether the public can actually get in, 724 sites yes, 4 by
appointment only, and the rest unknown or no.

```sql
SELECT SITE_NAME, ACRES, DISTRICT
FROM read_parquet('boston-open-space.parquet')
WHERE POS = 'X' AND PA = 'X'
ORDER BY ACRES DESC LIMIT 5;
```

## Limitations

A planning inventory, not a legal record. The city's own disclaimer
limits it to general planning, only deeds research and surveys settle
boundaries. It also is not a complete greenspace layer, street trees,
most schoolyards, and private yards are absent. This is a fixed
snapshot from July 2026 of a continuously edited layer, and it carries
no stable public identifier, so joins to later versions go through
`SITE_NAME` or space.

## Provenance and License

License, PDDL-1.0.
Providers, City of Boston (producer, licensor), Portolan SDI (host).
Original source, https://opendata.arcgis.com/api/v3/datasets/2868d370c55d4d458d4ae2224ef8cddd_7/downloads/data?format=shp&spatialRefId=4326 .
Features, 1,012. Cloud-native asset, boston-open-space.parquet (GeoParquet 2.0).
The upstream source is a live endpoint, so it is referenced by URL only and not archived as a source asset.
