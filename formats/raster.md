# Raster Data Format Requirements

## Supported Formats

Raster data **MUST** be provided in at least one of the following cloud-native formats:

- **Cloud Optimized GeoTIFF (COG)** — see [Cloud Optimized GeoTIFF](#cloud-optimized-geotiff-cog)
- **raquet** — see [raquet](#raquet)

A dataset **MAY** provide both: COG for GDAL/GIS tooling and web tiling, and raquet for
SQL- and Iceberg-native analysis. Both are represented as collection-level assets (see
[Collection-Level Assets](#collection-level-assets)).

### Cloud Optimized GeoTIFF (COG)

- **MAY** provide data in Cloud Optimized GeoTIFF (COG) format
  - Follows the [COG specification](https://www.cogeo.org/)
  - Enables efficient range-request access without full download
  - The natural choice when consumers use GDAL-based tooling, traditional GIS, or
    web map tiling pipelines

### raquet

- **MAY** provide data in raquet format
  - raquet stores raster blocks in [GeoParquet](https://geoparquet.org/), spatially
    indexed by [QUADBIN](https://docs.carto.com/data-and-analysis/analytics-toolbox-for-bigquery/key-concepts/spatial-indexes#quadbin)
    cell, so a raster lives in the same cloud-native, SQL-queryable model as Portolan
    vector data
  - Read directly with DuckDB via the `read_raquet` community extension, and registrable
    as an Apache Iceberg table — rasters can then be sampled and joined alongside vector
    tables in a single query, without a tile server or GDAL
  - The natural choice when consumers work in SQL / Iceberg-native analysis and want
    rasters in the same engine as their vectors

When choosing between the two: prefer **COG** for GDAL/GIS interoperability and web
tiling; prefer **raquet** for SQL- and Iceberg-native analysis. Providing both maximizes
reach.

## Collection-Level Assets

When a raster dataset is represented as a single file (COG, raquet, or both), each
representation **MUST** be a collection-level asset rather than wrapped in a STAC item,
mirroring the convention for [single-file vector datasets](vector.md#collection-level-assets).

```json
{
  "type": "Collection",
  "id": "elevation",
  "assets": {
    "cog": {
      "href": "./elevation.tif",
      "type": "image/tiff; application=geotiff; profile=cloud-optimized",
      "roles": ["data"]
    },
    "raquet": {
      "href": "./elevation.parquet",
      "type": "application/vnd.apache.parquet",
      "roles": ["data"]
    }
  }
}
```

A raquet asset uses the GeoParquet media type (`application/vnd.apache.parquet`); a COG
asset uses the Cloud Optimized GeoTIFF media type
(`image/tiff; application=geotiff; profile=cloud-optimized`). At least one `data`-role
asset **MUST** be present.

## Status

This format addendum is being developed alongside reference raster dataset
implementations. The raquet representation is additive: COG remains fully supported, and
catalogs **MAY** continue to publish raster data as COG alone.
