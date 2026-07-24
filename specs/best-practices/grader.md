# Best Practices — The Grader

Conformance is pass/fail: a catalog passes the validator or it does not. Above
that floor, quality is a scale, and this rubric grades it from A+ to F. Every
criterion below is checkable by inspection — a file resolves or 404s, a field
is present or absent, a count matches or disagrees — so two reviewers reach
the same grade.

One principle drives the weighting: **grade the machine contract as hard as
the visible surface.** The two decouple in practice. A catalog can ship
resolving thumbnails, thematic styles, and excellent prose while carrying no
checksums, empty provider lists, and no agent links. Humans notice the first
set. Agents and validators depend on the second. A rubric that rewards only
what a browser shows will certify catalogs that fail every machine that reads
them.

## How to read the tiers

Each dimension below anchors three tiers. **A+** is the ceiling worth aiming
at. **B** is solid: complete with minor defects. **D** is broken in a way that
blocks a class of consumers. Grades between the anchors interpolate: a C is a
mix of B and D findings, an A meets every B criterion and most of A+. **F** is
reserved for a catalog missing a required file class outright or whose
structural links are broken at scale.

## 1. Required files and links

- **A+** — `catalog.json`, `AGENTS.md`, and `README.md` exist and resolve at
  the root, every sub-catalog, and every collection. Each `AGENTS.md` is
  linked with `rel: "agents"` and each `README.md` with `rel: "describedby"`,
  both typed `text/markdown` and pointing at the raw file. Every catalog and
  collection declares the Portolan schema URI. Structural links are relative;
  no object carries a `self` link.
- **B** — All files exist and resolve, with scattered defects: a wrong media
  type on a `describedby` link, a missing schema URI on some objects, a stray
  `self` link.
- **D** — A file class is absent across the catalog (every `AGENTS.md` 404s,
  or the links to them are missing), the schema URI appears nowhere, or
  hardcoded `self` links pin every object to one deployment URL.

## 2. Metadata integrity

- **A+** — Every asset carries `file:checksum` and `file:size` with the
  registered media type for its format. Every collection lists a producer and
  exactly one host provider, the host reachable by URL or email. Licenses are
  valid SPDX identifiers, and mirrors carry `updated`.
- **B** — Providers, licenses, and media types are in order, but checksums are
  missing on some assets or `updated` has gone stale.
- **D** — Checksum coverage is zero, provider lists are empty (so the catalog
  has no owner and no contact), a forbidden license value like `proprietary`
  appears, or most data assets carry an unregistered media type.

## 3. Cloud-native assets

- **A+** — The primary data asset of every collection is cloud-native
  (GeoParquet, COG, PMTiles, COPC) with the correct media type, a visual
  derivative exists wherever the source is not self-rendering, legacy formats
  appear only as clearly-roled alternates, and each file is registered exactly
  once.
- **B** — Cloud-native primaries and visuals throughout, with a mislabeled
  media type or a legacy file registered as a plain extra asset.
- **D** — Primaries typed `application/octet-stream` or in server-dependent
  formats, duplicate asset keys pointing at one file with conflicting roles,
  or a geospatial collection with no renderable asset at all.

## 4. Agent documentation

- **A+** — Every `AGENTS.md` is dataset-specific: it names join keys, shows
  runnable remote queries against published URLs, states the CRS with its
  practical consequences, documents quirks the schema cannot express, offers
  non-trivial query recipes, and points at related collections.
- **B** — Present and linked at every level, but thin: access snippets and a
  schema restatement without quirks, recipes, or cross-references.
- **D** — Boilerplate repeated across collections, or content that contradicts
  the machine metadata it describes.

## 5. Visualization

- **A+** — Every geospatial collection has a thumbnail that resolves and was
  rendered from its default style, plus at least one style asset per render
  path with the default listed first. Rich collections offer thematic
  variants, per the [styling guidance](styling.md).
- **B** — A resolving thumbnail and a single default style on every
  collection, nothing more.
- **D** — Geospatial collections missing a thumbnail or a style entirely, or
  thumbnail links that 404.

## 6. Maintenance signals

- **A+** — `updated` is set and recent on every synced object, mirrors carry
  `via` and (where upstream publishes STAC) `canonical` links to specific
  upstream endpoints, the host is contactable, and prose agrees with metadata
  everywhere: counts, licenses, and links say the same thing in the README,
  the AGENTS.md, and the JSON.
- **B** — Provenance links are specific and honest, but `updated` lags or
  appears only at some levels.
- **D** — `updated` is null across a mirror, no contact route exists, or the
  documentation contradicts the metadata: a README table listing collections
  that 404, counts that disagree between levels, a guide claiming one license
  while the JSON declares another.

## The overall grade

A catalog's overall grade is its weakest dimension, raised by at most one step
when most other dimensions sit at A or better. The floor rule is the point:
excellence in visible dimensions cannot buy back a broken machine contract,
because the consumers who depend on that contract never see the polish.
