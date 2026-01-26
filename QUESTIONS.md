# Open Questions

This document tracks unresolved design questions for the Portolan specification. These require discussion and consensus among the core team before being resolved.

## Metadata & Documentation

- [ ] **Metadata format**: Should metadata live in Parquet files, README files, both, or elsewhere? What's required vs. best practice?
- [ ] **README template**: What are the minimum required fields/sections for a catalog README?
- [ ] **Column descriptions**: Should column descriptions be a core requirement or remain a best practice long-term?

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
