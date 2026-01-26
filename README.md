# Portolan Specification

Portolan is a STAC profile—not a competing specification. It adds requirements and best practices on top of [STAC](https://stacspec.org/) for publishing cloud-native geospatial data.

## What is Portolan?

Portolan provides a standardized way for municipalities, NGOs, and other organizations to share open geospatial data with:

- **Sovereignty**: Full control over your data and infrastructure
- **Low cost**: No servers required—static files on object storage
- **AI-accessible**: Structured metadata that LLMs and agents can understand
- **Cloud-native**: Built on modern formats like GeoParquet, COG, and COPC

## Specification

- [Core requirements](core.md) - Mandatory requirements for all Portolan catalogs
- [Format addenda](formats/) - Per-format specifications
  - [Vector data](formats/vector.md)
  - [Raster data](formats/raster.md)
  - [Point clouds](formats/pointcloud.md)
- [Best practices](best-practices.md) - Recommended conventions
- [Architectural decisions](DECISIONS.md) - Key design decisions and rationale
- [Process](process.md) - How we develop this spec

## Examples

See [examples/](examples/) for reference implementations.
