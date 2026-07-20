# Portolan Specification

Portolan is a specification for sharing geospatial data as cloud-native files on
object storage — no servers, no databases, no proprietary formats. A Portolan
catalog is a directory of open-format data described by structured
[STAC](https://stacspec.org/) metadata, hosted on any S3-compatible bucket.

Because the data is just files and the metadata is plain text, a browser, a query
engine like DuckDB, or an AI agent can read a catalog, understand what it holds,
and analyze it directly — with no service in between. If Portolan disappeared
tomorrow, every file in a catalog would still work in the tools people already use.

## Why

Portolan builds on existing standards rather than reinventing them: it is STAC
1.1.0 at its core, and reuses established STAC extensions wherever they fit. What
Portolan adds is a set of strong, opinionated requirements — on formats,
statistics, structure, and documentation — that make a catalog reliably usable by
both humans and agents without a server to interpret it.

It is deliberately prescriptive where that buys interoperability, and it evolves as
cloud-native tooling matures: requirements that are aspirational today may relax or
tighten as the ecosystem catches up. Conformance is defined not by declaration but
by passing the Portolan validator.

## Repository layout

| Path | What's there |
|------|--------------|
| [`specs/portolan/core.md`](specs/portolan/core.md) | The normative spec: catalog structure, conformance, links, providers, provenance, licensing, documentation, visualization — everything that isn't format-specific. |
| [`specs/portolan/formats.md`](specs/portolan/formats.md) | Format requirements: vector (GeoParquet + PMTiles), raster (COG), tabular (Parquet), point cloud (COPC). |
| [`specs/incubating/`](specs/incubating/) | Ad-hoc specs being formalized but not yet normative (raster styling, point clouds, GeoTIFF stats encoding, STAC-GeoParquet). |
| [`specs/best-practices/`](specs/best-practices/) | Non-normative guidance for people and agents, and the future home of the catalog grader. |
| [`stac/`](stac/) | The Portolan STAC profile and JSON schemas (in progress). |
| [`examples/`](examples/) | Working reference catalogs (pending). |

The normative keywords (MUST, SHOULD, MAY, …) throughout the spec are used as
defined in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174).

## Versioning

The specification is versioned with [SemVer](https://semver.org/), starting pre-1.0.
A catalog declares the version it was authored against through the **Portolan STAC
profile schema URI** in its `stac_extensions` array — e.g.
`https://portolan-sdi.org/portolan/v0.1.0/schema.json`. That schema URI is the
single signal of specification version; there is no separate version file (see
[Conformance and Versioning](specs/portolan/core.md#conformance-and-versioning)).

**Bump policy while pre-1.0:** any breaking change bumps the MINOR version (e.g.
`0.1.0` → `0.2.0`); non-breaking changes bump the PATCH. Once the spec reaches
`1.0.0`, normal SemVer applies. A change is **breaking** when a catalog that
conformed to the previous version may no longer conform, or a tool built against
the previous version may misvalidate — e.g. raising a rule's severity, adding a new
required field, or removing/renaming a field or accepted value. A change is
**non-breaking** when previously-conforming catalogs still conform — e.g. adding a
warning, relaxing a constraint, or editorial clarification.

## Contributing

The spec is developed here, in the open, as the record of the decisions behind
Portolan.

- **Propose a change** by opening a pull request. Discussion happens in the PR.
- **Raise a question or a disagreement** by opening an issue. Points that need more
  debate move to issues rather than blocking a release.
- **Immature ideas** live in [`specs/incubating/`](specs/incubating/) until they
  stabilize; **guidance and philosophy** live in
  [`specs/best-practices/`](specs/best-practices/).

When a change is normative, bump the spec version per the [bump
policy](#versioning) in the same PR.

See also the [Code of Conduct](CODE_OF_CONDUCT.md).
