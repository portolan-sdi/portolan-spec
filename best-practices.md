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

### Join Relationships

When geometry and attribute data are in separate files:

- **SHOULD** document the join columns explicitly in the README
- **SHOULD** include a working code example showing how to join the files

Example:

```markdown
## Data Structure

Geometry and attribute data are stored separately:
- `departamentos.parquet` - polygon geometries with `codigo_depto` key
- `attributes.parquet` - demographic attributes with `codigo_depto` key

### Joining the data

```python
import geopandas as gpd
import pandas as pd

# Read files
geometry = gpd.read_parquet("departamentos.parquet")
attributes = pd.read_parquet("attributes.parquet")

# Join on codigo_depto
data = geometry.merge(attributes, on="codigo_depto")
```
```
