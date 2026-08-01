# San Francisco Addresses (EAS)

Point addresses from the City and County of San Francisco Enterprise Addressing System, a 5,000-feature extract of the official DataSF open data layer, converted to cloud-native GeoParquet with a PMTiles visualization. The source asset points at the full live DataSF layer.

Five thousand records from the
[Enterprise Addressing System](https://data.sfgov.org/Geographic-Locations-and-Boundaries/Addresses-with-Units-Enterprise-Addressing-System/ramy-di5m),
San Francisco's master address database. Read this first, the full
layer holds 388,550 records and refreshes nightly, and this Collection
is deliberately a fixed 1.3 percent extract, the first 5,000 records
in the portal's internal order from the July 24, 2026 snapshot. It
exists to demonstrate the Portolan mirror pattern against a live
upstream at a size that keeps this reference catalog small. Query it
to learn the data's shape, then take real questions to the full layer.

The EAS is the city's operational address registry, aggregated from
the Department of Building Inspection, Planning, the Assessor's
Office, and the Department of Technology, and only DBI-approved
addresses enter it. Its rows have a grain worth understanding before
counting anything. One row is a base address, a unit, and a parcel
link, so a building appears once per unit and once per linked condo
parcel. The extract holds 4,488 distinct buildings under its 5,000
rows.

Agents, [AGENTS.md](./AGENTS.md) carries the row-grain rules and the
sentinel-value traps.

## Quick Start

```python
import geopandas as gpd

gdf = gpd.read_parquet("san-francisco-addresses.parquet")
print(gdf.head())
```

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column, so it needs a GeoPandas built on pyarrow 24 or newer. DuckDB spatial queries the same file in place, see [AGENTS.md](./AGENTS.md) for those patterns. Paths are relative to this directory, and the same code works against the published URL.

## Getting the Real Thing

The full live layer is one request away, the Socrata API serves it as
GeoJSON, CSV, or JSON pages.

```bash
curl 'https://data.sfgov.org/resource/ramy-di5m.json?$select=count(*)'
# 388550 as of July 2026
```

## Schema

| Column | Type | Description |
|---|---|---|
| `street_full_street_name` | varchar | Street name and type together. |
| `zip_code` | varchar | Five-digit ZIP code as a string. |
| `latitude` | varchar | Latitude as text. Prefer the geometry column. |
| `address_number_suffix` | varchar | Street number suffix such as A, null for nearly all rows. |
| `complete_landmark_name` | varchar | Landmark name for the few rows that carry one, Millennium Tower. |
| `eas_fullid` | varchar | Unique row identifier, base id, sub id, and parcel link id joined with dashes. The only column unique per row. |
| `direct_source` | varchar | Where the record entered the EAS, SF DBI, State of CA, or The Presidio Trust. |
| `cnn` | varchar | Centerline Network Number, the street-segment key of the city basemap, joins to the DataSF street centerlines. |
| `data_loaded_at` | timestamp with time zone | When the portal loaded the record. |
| `longitude` | varchar | Longitude as text. Prefer the geometry column. |
| `street_name` | varchar | Parsed street name. |
| `eas_baseid` | varchar | Identifier of the base address, the building. Units share it, so count distinct eas_baseid for buildings. |
| `nhood` | varchar | DataSF analysis neighborhood name, joins to the Analysis Neighborhoods dataset by name. |
| `block` | varchar | Assessor block number as a string. |
| `street_type` | varchar | Parsed street type, ST or AVE. Null for streets like BROADWAY that have no type. |
| `eas_subid` | varchar | Identifier of the sub-address, a unit or apartment, within its base. |
| `lot` | varchar | Assessor lot number as a string. |
| `address` | varchar | Full address string, with the unit as a hash suffix when present. |
| `unit_number` | varchar | Unit designator, null on base-address rows. |
| `supervisor` | varchar | Supervisor district number as a string. |
| `data_updated_at` | timestamp with time zone | Record update timestamp, with a 1970 epoch sentinel on never-updated rows. |
| `address_number` | varchar | Street number. |
| `parcel_number` | varchar | Assessor parcel number, block plus lot. Null on 32 percent of rows, a parcel join drops them silently. |
| `data_as_of` | timestamp with time zone | Snapshot timestamp of the upstream export, July 24, 2026 for every row here. |
| `geom` | geometry | Address point, WGS84 longitude and latitude. Units stack on their building's single point. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Per-feature bounding box struct, the GeoParquet covering. |

The table has 32 columns in all. The full list with types lives in `table:columns` on the `data` asset.

## Suggested Uses

Demonstrating and testing address-data patterns, base-versus-unit
modeling, parcel joins on `parcel_number` to DataSF's parcels layer,
neighborhood rollups on `nhood`, at a size where every query is
instant. The upstream EAS itself feeds DBI permitting and the
Planning Department's Property Information Map.

## Limitations

Wrong for any question about San Francisco itself. Geocoding against
it misses about 98.7 percent of the city's addresses, per-area counts
reflect sample order rather than density, and the snapshot ages while
upstream changes nightly. Points sit at building entrances, not
parcel centroids, and a third of rows carry no parcel link at all.
Presence of a unit record says nothing about occupancy or mail
deliverability.

## Provenance and License

License, PDDL-1.0.
Providers, City and County of San Francisco (producer, licensor), DataSF (processor), Portolan SDI (host).
Original source, https://data.sfgov.org/resource/ramy-di5m.geojson?$limit=5000&$order=:id .
Features, 5,000. Cloud-native asset, san-francisco-addresses.parquet (GeoParquet 2.0).
The upstream source is a live endpoint, so it is referenced by URL only and not archived as a source asset.
