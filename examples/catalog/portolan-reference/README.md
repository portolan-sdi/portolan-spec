# Portolan Reference Catalog

A mixed reference catalog exercising every major case in the Portolan v0.1 specification with real, openly licensed data pulled from its original upstream sources, vector polygons and points, raster, tabular, mirror provenance, nested catalogs and flat collections.

Every Collection here is a mirror that cites its true upstream source
with a real checksum, and every README and AGENTS.md is written to the
standard in the spec's documentation best practices, so the catalog
doubles as the worked example of what good catalog documentation looks
like. The Netherlands provinces Collection also mirrors its upstream ISO
19115 record as a metadata-role asset, and every code block in these
docs is executed by the repository's checks before it publishes.

Agents, each Collection carries its own AGENTS.md with join keys, quirks,
and tested queries, and the catalog-level [AGENTS.md](./AGENTS.md) maps
the joins between Collections.

## Collections

| Collection | Contents | Description |
|---|---|---|
| [Natural Earth Countries (1:110m)](./reference/natural-earth-countries/README.md) | 177 polygons | 177 country polygons at world scale, the public domain basemap behind most web choropleths. |
| [Natural Earth Populated Places (1:50m)](./reference/natural-earth-populated-places/README.md) | 1,251 points | 1,251 curated city and town points with population estimates, from Tokyo to Antarctic research stations. |
| [United States Counties (2023, 1:500k)](./boundaries/us-counties/README.md) | 3,235 polygons | All 3,235 county and equivalent boundaries as of January 1, 2023, keyed by the FIPS codes that unlock US county statistics. |
| [Boston Open Space](./boundaries/boston-open-space/README.md) | 1,012 polygons | 1,012 open space polygons of conservation and recreation interest, regardless of ownership, from Franklin Park to community gardens. |
| [Netherlands Provinces](./boundaries/netherlands-provinces/README.md) | 12 polygons | The 12 provinces from the cadastral registry, boundaries that reproduce the national statistics office's official areas to one decimal. |
| [San Francisco Addresses (EAS)](./mirror/san-francisco-addresses/README.md) | 5,000 points | A fixed 5,000-record extract of San Francisco's 388,550-record master address database, kept small on purpose for spec demonstration. |
| [Sample Raster COG](./raster/sample-cog/README.md) | 3-band raster | A 1 MB Landsat-derived reference COG for learning and testing cloud-optimized raster access, not for analysis. |
| [Eurostat Electricity Prices for Household Consumers](./tabular/eurostat-electricity-prices/README.md) | 65,412 rows | 65,412 semi-annual household electricity prices for 41 European countries from 2007 on, the official record of the 2022 energy crisis. |

## Where the Data Comes From

Licenses, CC-BY-4.0, CC0-1.0, PDDL-1.0.
Provenance, 8 mirror Collections.

Upstream sources.

- Natural Earth Countries (1:110m), https://naciscdn.org/naturalearth/110m/cultural/ne_110m_admin_0_countries.zip
- Natural Earth Populated Places (1:50m), https://naciscdn.org/naturalearth/50m/cultural/ne_50m_populated_places.zip
- United States Counties (2023, 1:500k), https://www2.census.gov/geo/tiger/GENZ2023/shp/cb_2023_us_county_500k.zip
- Boston Open Space, https://opendata.arcgis.com/api/v3/datasets/2868d370c55d4d458d4ae2224ef8cddd_7/downloads/data?format=shp&spatialRefId=4326
- Netherlands Provinces, https://service.pdok.nl/kadaster/brk-bestuurlijke-gebieden/atom/downloads/BestuurlijkeGebieden_2026.gpkg
- San Francisco Addresses (EAS), https://data.sfgov.org/resource/ramy-di5m.geojson?$limit=5000&$order=:id
- Sample Raster COG, https://raw.githubusercontent.com/rasterio/rasterio/main/tests/data/RGB.byte.tif
- Eurostat Electricity Prices for Household Consumers, https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/nrg_pc_204/?format=SDMX-CSV&compressed=false
