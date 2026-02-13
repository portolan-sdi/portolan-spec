# Recognized File Extensions

Portolan tools classify files by extension to determine how they should be handled during import and validation.

## Primary Geospatial Formats

These extensions are recognized as importable geospatial data:

| Extension | Format | Type | Cloud-Native |
|-----------|--------|------|--------------|
| `.parquet` | GeoParquet | Vector | Yes |
| `.geojson` | GeoJSON | Vector | No (converts to GeoParquet) |
| `.shp` | Shapefile | Vector | No (converts to GeoParquet) |
| `.gpkg` | GeoPackage | Vector | No (converts to GeoParquet) |
| `.fgb` | FlatGeobuf | Vector | No (converts to GeoParquet) |
| `.tif`, `.tiff` | GeoTIFF/COG | Raster | Depends (validates/converts to COG) |
| `.jp2` | JPEG2000 | Raster | No (converts to COG) |

Files with these extensions are candidates for `portolan dataset add`.

## Sidecar Files

These extensions are recognized as sidecar files belonging to a primary asset:

| Extension | Associated Format |
|-----------|-------------------|
| `.dbf` | Shapefile attribute table |
| `.shx` | Shapefile index |
| `.prj` | Shapefile projection |
| `.cpg` | Shapefile code page |
| `.sbn`, `.sbx` | Shapefile spatial index |
| `.ovr` | Raster overview (pyramid) |
| `.xml` | Auxiliary metadata (aux.xml, etc.) |

Sidecar files are **not** imported directly. When importing a `.shp` file, its sidecars are read automatically.

## Visualization Formats

| Extension | Format | Description |
|-----------|--------|-------------|
| `.pmtiles` | PMTiles | Cloud-native vector tiles for web rendering |
| `.mbtiles` | MBTiles | SQLite-based tile archive |

These are **derivatives**, not primary data. PMTiles **SHOULD** be generated from GeoParquet for web display.

## Metadata Files

| Filename | Description |
|----------|-------------|
| `catalog.json` | STAC Catalog (root) |
| `collection.json` | STAC Collection |
| `versions.json` | Portolan version manifest |
| `style.json` | MapLibre/deck.gl style definition |

These files have semantic meaning and are not imported as datasets.

## Thumbnail/Preview

| Extension | Handling |
|-----------|----------|
| `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif` | Treated as thumbnails if < 1MB |

Small images are assumed to be previews, not raster data.

## Ignored Files

The following are skipped during directory scans:

| Pattern | Reason |
|---------|--------|
| `.exe`, `.dll`, `.so`, `.dylib` | Executables |
| `.pyc`, `.pyo`, `.class`, `.o`, `.obj` | Compiled files |
| `__pycache__/`, `.git/`, `.svn/`, `.hg/` | Build/VCS directories |
| `.idea/`, `.vscode/`, `node_modules/` | IDE/tooling directories |
| `.csv`, `.tsv`, `.xlsx`, `.xls` | Tabular data (not geospatial) |
| `.md`, `.txt`, `.rst`, `.html` | Documentation |

## Extension vs. Role

STAC uses **asset roles** to describe purpose, not file extensions. The extensions above are used for:
1. **Import classification** — determining if a file can be added as a dataset
2. **Format detection** — deciding which conversion pipeline to use

Once imported, the STAC asset's `roles` field (e.g., `["data"]`, `["thumbnail"]`) provides machine-readable semantics.
