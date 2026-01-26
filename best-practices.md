# Best Practices

These are recommended conventions, not requirements. Portolan linters will warn about deviations but will not fail validation.

## Visualization

- **SHOULD** include a thumbnail image generated from default styling
- **SHOULD** provide default styling via `style.json`
  - Compatible with MapLibre GL JS and deck.gl
  - Enables immediate visualization without custom configuration

## Documentation

- **SHOULD** include collection-level READMEs for datasets with:
  - Multiple years of data
  - Multiple source agencies or methodologies
  - Complex versioning or update schedules

## Metadata

- **SHOULD** provide machine-readable metadata in Parquet format for datasets with:
  - Many coded/categorical variables
  - Complex classification schemes
  - Variables requiring detailed definitions

- **SHOULD** include column descriptions
  - May become a core requirement as tooling matures
  - Helps AI systems and users understand data structure

## Multi-file Relationships

- TBD: Best practice for documenting join relationships between separate files
- See [QUESTIONS.md](QUESTIONS.md) for open discussion
