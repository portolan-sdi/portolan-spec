# Architectural Decision Records

This document captures key architectural decisions made during the development of the Portolan specification.

## Format

Each decision includes:
- **Decision**: What was decided
- **Context**: Why this decision was needed
- **Rationale**: Why this approach was chosen
- **Date**: When the decision was made
- **Status**: Accepted, Superseded, or Under Review

---

## Decisions

### PMTiles Recommended, Not Required

**Date**: 2026-02-09
**Status**: Accepted (may be superseded in future spec iterations)
**Reference**: [ADR-0003: Plugin Architecture](https://github.com/portolan-sdi/portolan-cli/blob/main/context/shared/adr/0003-plugin-architecture.md)

**Decision**: PMTiles is an optional plugin, not a core requirement. Missing PMTiles triggers validation warnings, not errors.

**Rationale**: PMTiles requires tippecanoe (external binary), which would burden users who only need data access. The plugin model keeps core installation lean while supporting web visualization for those who need it.

---

### Warn on Non-Cloud-Native Formats, But Allow in Catalog

**Date**: 2026-02-09
**Status**: Accepted (may be superseded in future spec iterations)
**Reference**: [ADR-0014: Accept Non-Cloud-Native Formats](https://github.com/portolan-sdi/portolan-cli/blob/main/context/shared/adr/0014-accept-non-cloud-native-formats.md)

**Decision**: Accept legacy formats (Shapefile, GeoJSON, TIFF) without automatic transformation. Display warnings encouraging cloud-native conversion, but don't block operations.

**Rationale**: Rejecting legacy formats creates adoption friction. Users have legitimate needs for compatibility, organizational standards, and testing. Warnings guide best practices without forcing premature decisions.

---

## Template for New Decisions

**Date**: YYYY-MM-DD
**Status**: Under Review | Accepted | Superseded

**Decision**: [What was decided]

**Context**: [Why this decision was needed]

**Rationale**: [Why this approach was chosen over alternatives]

**Consequences**: [What this decision enables or constraints]
