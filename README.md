# Portolan Specification

> **This repository is a read-only mirror.**
>
> The source of truth is [portolan-cli/spec](https://github.com/portolan-sdi/portolan-cli/tree/main/spec).
> To propose changes, open a PR in [portolan-cli](https://github.com/portolan-sdi/portolan-cli).
>
> See [ADR-0048](https://github.com/portolan-sdi/portolan-cli/blob/main/context/shared/adr/0048-cli-as-spec-source.md) for context.

---

Portolan is a STAC profile—not a competing specification. It adds requirements and best practices on top of [STAC](https://stacspec.org/) for publishing cloud-native geospatial data.

## What is Portolan?

Portolan provides a standardized way for municipalities, NGOs, and other organizations to share open geospatial data with:

- **Sovereignty**: Full control over your data and infrastructure
- **Low cost**: No servers required—static files on object storage
- **AI-accessible**: Structured metadata that LLMs and agents can understand
- **Cloud-native**: Built on modern formats like GeoParquet, COG, and COPC

## Specification

- [Core requirements](core.md) - Mandatory requirements for all Portolan catalogs
- [Catalog structure](structure.md) - Directory layout and file organization
- [Version manifest](versions.md) - `versions.json` schema for version tracking
- [File extensions](extensions.md) - Recognized file types and classification
- [Format addenda](formats/) - Per-format specifications
  - [Vector data](formats/vector.md)
  - [Raster data](formats/raster.md)
  - [Point clouds](formats/pointcloud.md)
- [Best practices](best-practices.md) - Recommended conventions
- [Architectural decisions](DECISIONS.md) - Key design decisions and rationale

## Examples

See [examples/](examples/) for reference implementations.
