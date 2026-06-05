# Portolan Schemas

Machine-readable validation schemas for Portolan catalogs. These schemas are the authoritative source of truth for validation logic shared between the CLI and registry.

## Files

| File | Description |
|------|-------------|
| `versions.schema.json` | Schema for `versions.json` manifest files |
| `collection.schema.json` | Schema for STAC Collections with Portolan extensions |
| `catalog.schema.json` | Schema for STAC Catalogs with Portolan extensions |
| `rules.yaml` | Validation rules that cannot be expressed in JSON Schema |

## Usage

### Python (jsonschema)

```python
import json
from pathlib import Path
from jsonschema import validate, RefResolver

schema_dir = Path("schema")

# Load schema
with open(schema_dir / "versions.schema.json") as f:
    versions_schema = json.load(f)

# Validate versions.json
with open("my-collection/versions.json") as f:
    versions_data = json.load(f)

validate(instance=versions_data, schema=versions_schema)
```

### STAC Collection/Catalog Validation

The collection and catalog schemas extend STAC's official schemas via `$ref`. For full validation, you need network access to fetch the STAC schemas, or use a resolver with local copies:

```python
from jsonschema import validate, RefResolver
import requests

# Fetch STAC schemas (or use local copies)
resolver = RefResolver.from_schema(collection_schema)

validate(instance=collection_data, schema=collection_schema, resolver=resolver)
```

### CLI Integration

The Portolan CLI validates against these schemas in `tests/spec_compliance/`. See [portolan-cli](https://github.com/portolan-sdi/portolan-cli) for integration examples.

## rules.yaml

Some validation rules cannot be expressed in JSON Schema. These are documented in `rules.yaml` with:

- **id**: Unique rule identifier (e.g., `RULE-0001`)
- **level**: `error` or `warning`
- **scope**: Where the rule applies
- **validation**: Pseudo-code for implementation

Example rules:
- Asset hrefs must be absolute S3 URLs in published catalogs
- Collection IDs should follow naming conventions
- GeoParquet files must contain geo metadata

## Schema Versioning

Schemas follow the same versioning as the spec. The `spec_version` field in `versions.json` indicates which schema version applies.

## Contributing

New schema fields require CLI implementation first — see [CONTRIBUTING.md](../CONTRIBUTING.md) for the proposal process.

When updating schemas for implemented features:

1. Update the JSON Schema files
2. Update `rules.yaml` if needed
3. Ensure CLI tests pass against new schemas
4. Update prose documentation to match
