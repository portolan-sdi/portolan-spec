# Open Questions

This document tracks unresolved design questions for the Portolan specification. These require discussion and consensus among the core team before being resolved.

## Metadata & Documentation

- [ ] **Metadata format**: Should metadata live in Parquet files, README files, both, or elsewhere? What's required vs. best practice?
- [ ] **README template**: What are the minimum required fields/sections for a catalog README?
- [ ] **Column descriptions**: Should column descriptions be a core requirement or remain a best practice long-term?
- [ ] **Machine-readable metadata**: When datasets have many coded variables, is a parquet/CSV metadata file a best practice, or should we be more prescriptive? Context: Argentina census has dozens of coded variables; a metadata parquet file is queryable with DuckDB. README points to it rather than duplicating. Is this pattern worth standardizing?
- [ ] **Filename standardization**: Should we standardize filenames (e.g., `overview.pmtiles`, `metadata.parquet`) or just asset roles? The STAC asset roles field already provides machine-readable semantics—filenames could be best practice rather than spec.

## Visualization

- [ ] **Thumbnail generation approach**: What's the best way to generate thumbnails from local data? Playwright requires HTTP server for PMTiles; other approaches may not use style.json. Need to determine recommended tooling.
- [ ] **style.json requirement**: Should style.json be required if thumbnail can be generated without it?

## Data Relationships

- [ ] **Join documentation**: How should we document join relationships between separate files (e.g., geometry file + attribute file)?

## Versioning

- [ ] **versions.json format**: Is the current proposed format correct? What fields are required?
- [ ] **Portolan Node definition**: What exactly constitutes a "Portolan Node" vs. just a valid STAC catalog that happens to follow Portolan conventions?

## Licensing & Governance

- [ ] **License**: Should we use Apache 2.0 for tooling code and CC BY 4.0 for specification documents?
- [ ] **Extension mechanism**: Where and how can the community add new format types or custom fields without forking the spec?

## Future Considerations

- [ ] **Spec versioning**: How should we version the Portolan specification itself? Semantic versioning?
- [ ] **Certification/compliance**: Should there be formal compliance testing or certification for Portolan catalogs?
