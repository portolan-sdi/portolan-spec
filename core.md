# Core Requirements

These requirements apply to all Portolan catalogs, regardless of data format.

## STAC Compliance

- **MUST** be a valid STAC Catalog or Collection
- **MUST** follow STAC specification version 1.0.0 or later

## Root Documentation

- **MUST** include a `README.md` at the catalog root
- README content requirements: TBD (see [QUESTIONS.md](QUESTIONS.md))

## Versioning

- **MUST** include version tracking via:
  - `versions.json` manifest file
  - STAC link relations (rel: `predecessor-version`, `successor-version`, `latest-version`)
- Format of `versions.json`: TBD (see [QUESTIONS.md](QUESTIONS.md))

## Format-Specific Requirements

Additional requirements apply based on data type. See format addenda:

- [Vector data](formats/vector.md)
- [Raster data](formats/raster.md)
- [Point cloud data](formats/pointcloud.md)

Format addenda are normativethey define **MUST** requirements, not suggestions.
