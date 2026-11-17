# Portolan

Portolan makes geospatial data easy to publish and easy to use. A catalog is
plain files in your own storage, described so that a person or an agent can
understand the data and query it directly. Publishing works the same way whether
you are a satellite company releasing a planetary archive or a city publishing
local cadastral data. There are no servers, no databases, and no accounts.

Under the hood, Portolan is an opinionated specification for cloud-native
geospatial catalogs, plus the tooling around it. A catalog is a directory of
open-format data on any S3-compatible bucket, described by structured
[STAC](https://stacspec.org/) metadata and built on
[COG](https://cogeo.org/), [GeoParquet](https://geoparquet.org/),
[PMTiles](https://github.com/protomaps/pmtiles), [COPC](https://copc.io/), and
[GeoZarr](https://geozarr.org/). Each part of the tooling raises the value of the
others:

- **The specification** defines what a great catalog looks like. It lives here.
- **[rashid](https://github.com/portolan-sdi/rashid)**, the validator, proves a
  catalog meets the specification.
- **[portolan-cli](https://github.com/portolan-sdi/portolan-cli)** makes catalogs
  easy to build.
- **[The registry](https://github.com/portolan-sdi/portolan-registry)** connects
  catalogs into a searchable network.

If Portolan disappeared tomorrow, every file in a catalog would still work in the
tools people already use.

Portolan is not a platform. There is nothing to log into and nothing to depend
on. It is not a paid product either. The specification and the tools are open
source under Apache-2.0, and your only costs are storage and egress, paid to
your cloud provider.

This repository holds the specification. It is pre-1.0 and under active
development, and contributions are welcome.

## What a catalog looks like

Every catalog and collection carries `catalog.json` or `collection.json` for
machines, plus `README.md` and `AGENTS.md` for people and agents. Data assets sit
alongside the metadata that describes them.

```
catalog.json
README.md
AGENTS.md
boundaries/
  catalog.json
  README.md
  AGENTS.md
  us-counties/
    collection.json
    README.md
    AGENTS.md
    us-counties.parquet
    us-counties.pmtiles
    thumbnail.png
    styles/
      categorical.json
      labeled.json
```

Catalogs can nest. Collections sit one level deep and never nest inside each
other. A generated catalog covering vector, raster, tabular, and mirrored data
lives in [`examples/catalog/portolan-reference/`](examples/catalog/portolan-reference/).

## Portolan philosophy

Portolan builds on existing standards rather than reinventing them. It is STAC
1.1.0 at its core and reuses established STAC extensions wherever they fit. On
top of that, Portolan adds strong requirements on formats, statistics, structure,
and documentation, so people and agents can use a catalog directly from storage
with no server in between. The point is a higher quality bar. Working with any
Portolan catalog should be a good experience.

The specification is prescriptive where that supports interoperability, and it is
meant to evolve as cloud-native tooling matures. Core standards like STAC and
GeoParquet were built for long-term stability. Portolan sits on top of them and
moves faster. Each version states what the community currently believes a great
catalog looks like, so a requirement that is aspirational today may relax or
tighten as the ecosystem catches up. Conformance means passing the
[validator](https://github.com/portolan-sdi/rashid), not claiming to conform.
Every normative statement carries a stable ID in
[`requirements.yaml`](specs/portolan/requirements.yaml), and CI proves that
rashid enforces each one.

Where the current landscape has gaps, Portolan will incubate new specifications
or write down practices that until now have been informal. Usually that means
contributing to STAC extensions or adding new ones. It can also mean small,
independent specifications that capture current practice, which live in
[`specs/incubating/`](specs/incubating/) until they stabilize.

People and agents are treated as equals throughout. The best practices for
guiding agents are moving fast, so this part of the specification will keep
changing, but the aim is constant. A Portolan catalog should be low-friction for
a human analyst and an automated one alike. Building or mirroring a catalog
should be easy too, including with AI tools, because lowering the effort to
publish is how more good data gets published.

The specification leaves some judgment calls open, such as what one catalog
should contain and how to organize it.
[`specs/best-practices/philosophy.md`](specs/best-practices/philosophy.md) covers
those.

## Reading the spec

Start with [`specs/portolan/core.md`](specs/portolan/core.md) for catalog
structure, conformance, links, providers, provenance, licensing, documentation,
and visualization. Then read
[`specs/portolan/formats.md`](specs/portolan/formats.md) for what each format
requires.

Two things are worth knowing first. Portolan catalogs are static, so there is no
Portolan API to implement. The spec is also pre-1.0, so requirements still move
between versions.

The normative keywords (MUST, SHOULD, MAY, …) throughout the spec are used as
defined in [RFC 2119](https://www.rfc-editor.org/rfc/rfc2119) and
[RFC 8174](https://www.rfc-editor.org/rfc/rfc8174).

## Repository layout

| Path | What's there |
|------|--------------|
| [`specs/portolan/core.md`](specs/portolan/core.md) | The normative spec: catalog structure, conformance, links, providers, provenance, licensing, documentation, visualization. |
| [`specs/portolan/formats.md`](specs/portolan/formats.md) | Format requirements: vector (GeoParquet + PMTiles), raster (COG), tabular (Parquet), point cloud (COPC). |
| [`specs/incubating/`](specs/incubating/) | Ad-hoc specs formalized but not yet normative (raster styling, point clouds, GeoTIFF stats encoding, STAC-GeoParquet). |
| [`specs/best-practices/`](specs/best-practices/) | Non-normative guidance for people and agents. |
| [`specs/portolan/requirements.yaml`](specs/portolan/requirements.yaml) | The requirements manifest: a stable ID, severity, and quote for every normative statement, checked against the prose in CI. |
| [`stac/`](stac/) | The Portolan STAC profile and its JSON schemas. |
| [`examples/`](examples/) | Working reference catalogs, generated by [`examples/tools/build.py`](examples/tools/build.py). |
| [`CHANGELOG.md`](CHANGELOG.md) | What changed in each specification version. The STAC profile keeps its own in [`stac/CHANGELOG.md`](stac/CHANGELOG.md). |

## Versioning

The specification is versioned with [SemVer](https://semver.org/), starting
pre-1.0. A catalog declares the version it was authored against through the
**Portolan STAC profile schema URI** in its `stac_extensions` array, e.g.
`https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json`. That schema URI
is the single signal of specification version, and there is no separate version
file (see
[Conformance and Versioning](specs/portolan/core.md#conformance-and-versioning)).

**Bump policy while pre-1.0:** any breaking change bumps the MINOR version (e.g.
`0.1.0` → `0.2.0`), and non-breaking changes bump PATCH. Once the spec reaches
`1.0.0`, normal SemVer applies, with the carve-out below.

A change is **breaking** when a catalog that conformed to the previous version
may no longer conform, or when a tool built against the previous version may
misvalidate. A tool **misvalidates** when it reports an error against a
conforming catalog, or reports no error against a non-conforming one. A change
is **non-breaking** when neither test finds anything. Previously-conforming
catalogs still conform, and a tool built against the previous version returns
the verdicts it returned before.

| Change | What an old tool does | Verdict |
| --- | --- | --- |
| Raise a rule's severity | misses an error that is now due | breaking |
| Add a required field | misses an error that is now due | breaking |
| Remove or rename a field or accepted value | misses an error that is now due | breaking |
| Relax a constraint | reports an error against a catalog that now conforms | breaking |
| Add a warning | emits no warning, and no error was due | non-breaking |
| Clarify wording | returns the same verdicts | non-breaking |

**After `1.0.0`, a relaxation bumps MINOR, not MAJOR.** Normal SemVer maps a
break to MAJOR. A relaxation breaks tools alone, and every catalog that
conformed still conforms, so MINOR carries the signal at the right cost.

**A released schema is immutable.** Each release is a git tag, `vX.Y.Z`, and
the tag contains the JSON Schema for that version. The schema served at a
released URI never changes, so a catalog validates the same way in a year as on
the day it was published. Never move or delete a release tag.
[`publish-schema.yaml`](.github/workflows/publish-schema.yaml) rebuilds
`schemas.portolan-sdi.org` from the release tags alone and reads each schema
from its tag.

**`main` holds the draft of the next version.**
[`stac/json-schema/schema.json`](stac/json-schema/schema.json) is the one schema
file on `main`. The `version` field in [`stac/package.json`](stac/package.json)
names the next release, and every Portolan schema URI on `main` uses that
version. Nothing is served at that URI until its tag exists. The site never
serves the draft. So the `main` preview of the reference catalog, which
[`publish-catalogs.yaml`](.github/workflows/publish-catalogs.yaml) publishes,
declares a schema URI that does not resolve before the release.

### Releasing

A release follows these steps, in this order:

1. Open a release PR that updates [`CHANGELOG.md`](CHANGELOG.md) and
   [`stac/CHANGELOG.md`](stac/CHANGELOG.md). Check the version against the bump
   policy. If every change since the last release is non-breaking, move
   `version` and every schema URI to the next PATCH version in the same PR.
2. Merge the release PR. Tag the merge commit `v` plus the version, such as
   `v0.3.0`, and publish a GitHub release from the tag.
3. The release runs `publish-schema.yaml`. The workflow fails unless `version`
   in the tagged `stac/package.json` equals the tag without its `v`. After the
   deploy, it compares each served schema with its tagged bytes by SHA-256.
4. Release [rashid](https://github.com/portolan-sdi/rashid) with the new
   schema. Its `scripts/vendor_spec_fixtures.py` reads each release tag. Then
   bump the rashid pin in [`examples/tools/build.py`](examples/tools/build.py)
   and
   [`examples/tools/tests/check_validate.py`](examples/tools/tests/check_validate.py).
5. Open one PR that moves `version` in `stac/package.json` and every Portolan
   schema URI to the next MINOR version. `npm test` in `stac/` lists each URI
   that still references the old version.

## Contributing

The spec is developed in the open, and this repository records the decisions
behind Portolan.

- **Propose a change** by opening a pull request. Discussion happens in the PR.
- **Raise a question or a disagreement** by opening an issue. Points that need
  more debate move to issues rather than blocking a release.
- **Immature ideas** live in [`specs/incubating/`](specs/incubating/) until they
  stabilize, and **guidance and philosophy** live in
  [`specs/best-practices/`](specs/best-practices/).

A normative change does not bump the version, because `main` already names the
next release. Edit [`stac/json-schema/schema.json`](stac/json-schema/schema.json)
in the same PR as the prose it enforces. The [release steps](#releasing) set the
version.

### Companion validator PRs

The spec is ground truth and [rashid](https://github.com/portolan-sdi/rashid) is
its deterministic implementation. A catalog conforms to the spec exactly when it
passes rashid, so the two must never diverge.

Every PR that touches normative content (`specs/` or `stac/`) must name the
matching rashid PR in its body:

```
Companion-PR: portolan-sdi/rashid#123
```

CI verifies the reference. Editorial changes with no conformance impact (typos,
wording, formatting) can skip the requirement with the `no-validator-change`
label.

A spec PR can merge before rashid releases its companion PR. The checks in
this repository validate against the local
[`stac/json-schema/schema.json`](stac/json-schema/schema.json), not the schema
bundled in a rashid release. rashid bundles the new schema in the release that
follows the spec tag, as the [release steps](#releasing) describe.

## Community

- Website: [portolan-sdi.org](https://www.portolan-sdi.org/)
- Discussion: the [Portolan Google Group](https://groups.google.com/g/portolan)
- Chat: [#portolan](https://cloudnativegeo.slack.com/archives/C0A1JBH9529) in the
  Cloud-Native Geo Slack
- Roadmap: the [planning board](https://github.com/orgs/portolan-sdi/projects/1)

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).
