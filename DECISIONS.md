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

## ADR-001: Portolan as STAC Profile

**Date**: 2026-01-26
**Status**: Accepted

**Decision**: Portolan is defined as a profile of STAC (SpatioTemporal Asset Catalog), not a competing or independent specification.

**Context**: We needed to decide whether to build a new specification from scratch or extend an existing standard for geospatial catalog metadata.

**Rationale**:
- STAC is widely adopted and has extensive tooling ecosystem
- STAC already solves catalog structure, linking, and discovery
- Building on STAC lets us focus on our unique value: sovereignty, cost, and AI-accessibility
- Compatibility with STAC tooling provides immediate value to users

---

## ADR-002: Cloud-Native Formats as Requirements

**Date**: 2026-01-26
**Status**: Accepted

**Decision**: Require cloud-native formats (GeoParquet, COG, COPC) rather than allowing traditional formats (Shapefile, GeoTIFF, LAS).

**Context**: We needed to decide whether to mandate specific file formats or be format-agnostic.

**Rationale**:
- Cloud-native formats enable efficient range-request access without full downloads
- Reduces cost by minimizing data transfer and compute requirements
- Essential for "no server required" goal
- Traditional formats require full downloads or complex server infrastructure

---

## ADR-003: Separation of Core Requirements and Best Practices

**Date**: 2026-01-26
**Status**: Accepted

**Decision**: Separate mandatory requirements (core.md, formats/*.md) from recommended best practices (best-practices.md).

**Context**: Some conventions improve catalogs but shouldn't block publication. We needed a way to guide without mandating everything.

**Rationale**:
- Lowers barrier to entry—publishers can start with minimal requirements
- Best practices can evolve faster without spec changes
- Linters can warn on best practices without failing validation
- Allows community to propose and adopt conventions organically

---

## ADR-004: Format-Specific Addenda

**Date**: 2026-01-26
**Status**: Accepted

**Decision**: Create separate format addenda (formats/vector.md, formats/raster.md, etc.) rather than putting all format requirements in core.md.

**Context**: Different data types (vector, raster, point cloud) have different requirements and best practices.

**Rationale**:
- Modular structure allows format-specific requirements to evolve independently
- Publishers can focus on relevant formats without noise from other types
- Makes it easier to add new format types as community needs them
- Clear extension point for community contributions

---

## Template for New Decisions

**Date**: YYYY-MM-DD
**Status**: Under Review | Accepted | Superseded

**Decision**: [What was decided]

**Context**: [Why this decision was needed]

**Rationale**: [Why this approach was chosen over alternatives]

**Consequences**: [What this decision enables or constrains]
