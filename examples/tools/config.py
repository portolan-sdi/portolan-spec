"""Static configuration for the Portolan reference generator.

Extension schema URIs, media types, and the shared categorical palette. No
logic, no catalog-specific values.
"""
from __future__ import annotations

SCHEMA_URI = "https://schemas.portolan-sdi.org/portolan/v0.1.0/schema.json"
FILE_EXT = "https://stac-extensions.github.io/file/v2.1.0/schema.json"
WEBMAP_EXT = "https://stac-extensions.github.io/web-map-links/v1.3.0/schema.json"
RASTER_EXT = "https://stac-extensions.github.io/raster/v2.0.0/schema.json"
TABLE_EXT = "https://stac-extensions.github.io/table/v1.2.0/schema.json"
PROJ_EXT = "https://stac-extensions.github.io/projection/v2.0.0/schema.json"
ATTRIBUTION_EXT = "https://stac-extensions.github.io/attribution/v0.1.0/schema.json"
STAC_VERSION = "1.1.0"

MEDIA = {
    "geoparquet": "application/vnd.apache.parquet",
    "parquet": "application/vnd.apache.parquet",
    "cog": "image/tiff; application=geotiff; profile=cloud-optimized",
    "pmtiles": "application/vnd.pmtiles",
    "style": "application/vnd.mapbox.style+json",
    "png": "image/png",
}

# Categorical palette shared by the thumbnails and the MapLibre styles, so a
# collection reads the same across both. Tableau 10 minus grey.
PALETTE = ["#4e79a7", "#f28e2b", "#59a14f", "#e15759", "#b07aa1",
           "#76b7b2", "#edc948", "#ff9da7"]
