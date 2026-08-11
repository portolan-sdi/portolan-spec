# Administrative Boundaries

Administrative and open-space boundary Collections from official sources.

## Collections

| Collection | Contents | Description |
|---|---|---|
| [United States Counties (2023, 1:500k)](./us-counties/README.md) | 3,235 polygons | All 3,235 county and equivalent boundaries as of January 1, 2023, keyed by the FIPS codes that unlock US county statistics. |
| [Boston Open Space](./boston-open-space/README.md) | 1,012 polygons | 1,012 open space polygons of conservation and recreation interest, regardless of ownership, from Franklin Park to community gardens. |
| [Netherlands Provinces](./netherlands-provinces/README.md) | 12 polygons | The 12 provinces from the cadastral registry, boundaries that reproduce the national statistics office's official areas to one decimal. |

## Where the Data Comes From

All 3 Collections here are mirrors, so this catalog hosts copies of data produced elsewhere.

United States Counties (2023, 1:500k) is built from the [US Census cartographic boundary counties 2023 500k (zipped Shapefile)](https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip), pinned by checksum and licensed CC0-1.0.
Boston Open Space tracks the [City of Boston Open Space (zipped Shapefile export)](https://opendata.arcgis.com/api/v3/datasets/2868d370c55d4d458d4ae2224ef8cddd_7/downloads/data?format=shp&spatialRefId=4326), a live endpoint refetched on every build rather than pinned, licensed PDDL-1.0.
Netherlands Provinces is built from the [PDOK Bestuurlijke Gebieden 2026 (GeoPackage)](https://service.pdok.nl/kadaster/brk-bestuurlijke-gebieden/atom/downloads/BestuurlijkeGebieden_2026.gpkg), pinned by checksum and licensed CC-BY-4.0.
