# Portolan STAC Profile

> **Scaffold — work in progress.** This directory will hold the Portolan STAC
> profile and any Portolan-specific STAC extension schemas. It is being authored
> separately; this README marks the slot in the repo structure.

Portolan is a [STAC](https://stacspec.org/) profile: it constrains and extends STAC
1.1.0 rather than competing with it. This directory is the normative home for that
profile — the machine-readable counterpart to the prose in
[`specs/portolan/`](../specs/portolan/).

## Intended layout

Following the pattern of the [CEOS-ARD STAC
extension](https://github.com/stac-extensions), this directory will contain:

- **`README.md`** (this file) — the profile itself: which STAC extensions Portolan
  requires versus recommends, the exact schema URIs and versions to pin, and how
  they are used. This is the source referenced by
  [`core.md` → Recommended STAC Extensions](../specs/portolan/core.md#recommended-stac-extensions).
- **`json-schema/`** — JSON Schema documents for any Portolan-specific extension
  fields, published under `portolan-sdi.org` and declared in a catalog's
  `stac_extensions` array (e.g. `https://portolan-sdi.org/portolan/v0.1.0/schema.json`).

## Status

The profile content is under active development. Until it lands here, the normative
requirements are the prose in [`specs/portolan/`](../specs/portolan/).
