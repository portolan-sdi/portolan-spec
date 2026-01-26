# Core Requirements

These requirements apply to all Portolan catalogs, regardless of data format.

## STAC Compliance

- **MUST** be a valid STAC Catalog or Collection
- **MUST** follow STAC specification version 1.0.0 or later

## Data Storage

Portolan catalogs assume data is hosted in S3-compatible object storage. This is the ground truth for all assets.

## Asset URLs

Asset hrefs **MUST** be absolute S3 URLs:

```json
"assets": {
  "data": {
    "href": "https://bucket-name.s3.region.amazonaws.com/path/to/file.parquet",
    "type": "application/vnd.apache.parquet",
    "roles": ["data"]
  }
}
```

## Link Paths

STAC link relations (`root`, `self`, `child`, `parent`) **SHOULD** use relative paths within the catalog structure:

```json
"links": [
  {"rel": "root", "href": "./catalog.json", "type": "application/json"},
  {"rel": "self", "href": "./collection.json", "type": "application/json"},
  {"rel": "child", "href": "./2022/collection.json", "type": "application/json"}
]
```

This keeps the catalog portable if mirrored to a different bucket.

## Providers

**SHOULD** use STAC-standard `providers` array:

```json
"providers": [
  {
    "name": "Organization Name",
    "roles": ["producer"],
    "url": "https://example.com"
  }
]
```

## Root Documentation

- **MUST** include a `README.md` at the catalog root
- README content requirements: TBD (see [QUESTIONS.md](QUESTIONS.md))

## Versioning

- **MUST** include version tracking via:
  - `versions.json` manifest file
  - STAC link relations (rel: `predecessor-version`, `successor-version`, `latest-version`)
- Format of `versions.json`: TBD (see [QUESTIONS.md](QUESTIONS.md))

If versioning is used, **SHOULD** include a link to versions.json:

```json
{
  "rel": "version-history",
  "href": "./versions.json",
  "type": "application/json"
}
```

## Format-Specific Requirements

Additional requirements apply based on data type. See format addenda:

- [Vector data](formats/vector.md)
- [Raster data](formats/raster.md)
- [Point cloud data](formats/pointcloud.md)

Format addenda are normativethey define **MUST** requirements, not suggestions.
