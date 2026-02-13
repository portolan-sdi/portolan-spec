# Catalog Structure

A Portolan catalog is a directory containing a `.portolan` folder with STAC metadata and cloud-native geospatial data.

## Directory Layout

```
project/
└── .portolan/
    ├── catalog.json
    └── collections/
        └── {collection_id}/
            ├── collection.json
            ├── versions.json
            └── {item_id}/
                └── {filename}.parquet
```

## Root Level

| File | Required | Description |
|------|----------|-------------|
| `catalog.json` | **MUST** | STAC Catalog (root metadata) |
| `collections/` | **MUST** | Directory containing all collections |

The `.portolan` directory **MUST** exist at the project root. Tools **SHOULD** create this directory via `portolan init`.

## Collection Level

Each collection is a subdirectory of `collections/` named with the collection ID.

| File | Required | Description |
|------|----------|-------------|
| `collection.json` | **MUST** | STAC Collection metadata |
| `versions.json` | **MUST** | Version history and checksums (see [versions.md](versions.md)) |
| `{item_id}/` | — | One directory per dataset item |

Collection IDs **MUST**:
- Contain only lowercase letters, numbers, hyphens, and underscores
- Start with a letter
- Be unique within the catalog

## Item Level

Each item is a subdirectory of the collection named with the item ID.

| File | Required | Description |
|------|----------|-------------|
| Primary data asset | **MUST** | One of: `.parquet` (vector), `.tif` (raster), `.copc.laz` (point cloud) |
| `{item_id}.pmtiles` | **SHOULD** | Vector tile derivative for web display (vector only) |
| `thumbnail.png` | **SHOULD** | Preview image (any format: `.png`, `.jpg`, `.webp`) |
| `style.json` | **MAY** | MapLibre-compatible styling |

Item IDs **SHOULD** derive from the source filename stem (e.g., `census.shp` → item ID `census`).

## Flat Hierarchy

Portolan catalogs use a **flat hierarchy**: collections contain items directly, with no nested sub-collections.

```
# Correct (flat)
.portolan/collections/census-2020/tracts/tracts.parquet
.portolan/collections/census-2020/blocks/blocks.parquet

# Incorrect (nested)
.portolan/collections/census/2020/tracts/tracts.parquet
```

This simplifies tooling and avoids ambiguity about where versioning boundaries lie.

## STAC Catalog Type

Portolan catalogs **MUST** be saved as `SELF_CONTAINED` (pystac terminology), meaning:
- All links use relative paths
- The catalog is portable across different hosting locations
- No absolute filesystem paths leak into metadata

## Example

A catalog with one vector dataset:

```
project/
├── .portolan/
│   ├── catalog.json
│   └── collections/
│       └── boundaries/
│           ├── collection.json
│           ├── versions.json
│           └── districts/
│               ├── districts.parquet
│               ├── districts.pmtiles
│               └── thumbnail.png
└── README.md
```
