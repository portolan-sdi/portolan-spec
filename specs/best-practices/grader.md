# Best Practices — The Grader

Conformance is pass/fail: a catalog passes the validator or it does not. Above
that floor, quality is a scale, and this rubric grades it from A+ to F.
Compliance alone does not make data good — "you can have perfectly FAIR,
utterly useless data" ([Sundwall,
2025](https://radiant.earth/blog/2025/11/great-data-products/)) — so the
rubric measures two different things. Grades up through A rest on criteria
checkable by inspection: a file resolves or 404s, a field is present or
absent, a count matches or disagrees, so two reviewers reach the same grade.
The A+ is a judgment call about whether the catalog is genuinely excellent to
use, and it is assessed qualitatively.

One principle drives the weighting: **grade the machine contract as hard as
the visible surface.** The two decouple in practice. A catalog can ship
resolving thumbnails, thematic styles, and excellent prose while carrying
empty provider lists and no agent links. Humans notice the first set. Agents
and validators depend on the second. A rubric that rewards only what a
browser shows will certify catalogs that fail every machine that reads them.

## The ladder

The grades anchor to the spec, so a publisher always knows what a given level
of effort earns:

- **F** — Not a validating STAC catalog. Malformed JSON, a missing or
  unreachable root, or structural links broken at scale. There is nothing
  here for a STAC client to consume.
- **D** — A real attempt, decently broken. The catalog validates as STAC but
  misses Portolan requirements in ways that block a class of consumers: a
  required file class absent throughout, no renderable assets, documentation
  that contradicts the metadata.
- **C** — Portolan-compliant, and nothing more. Every MUST in
  [core](../portolan/core.md) is met: the required files exist and link, the
  schema URI is declared, primaries are cloud-native. Conformance is the
  entry ticket, not the destination.
- **B** — Compliant plus the SHOULDs, executed with minor defects. Thumbnails
  and styles resolve, agent guides exist at every level, providers and
  licenses are in order.
- **A** — Everything checkable, done well. The catalog sits at the top tier
  of every dimension below: dataset-specific agent guides, multiple
  purposeful visualizations, a default view that renders, prose that agrees
  with metadata everywhere.
- **A+** — Beyond anything the spec names. The judgment-call grade, described
  in [its own section](#the-a-judgment): candid evaluation of limitations
  and biases, a narrative that gives real context, an experience that
  renders instantly and reads beautifully, and contribution back to the
  shared network. When a user shows up at this catalog, it is an incredible
  experience.

## How to read the tiers

Each dimension below anchors three tiers. **A** is the checkable ceiling.
**B** is solid: complete with minor defects. **D** is broken in a way that
blocks a class of consumers. Grades between the anchors interpolate: a C is a
mix of B and D findings. A catalog's checkable grade is capped by these
dimensions; the A+ sits above them all.

## 1. Required files and links

- **A** — `catalog.json`, `AGENTS.md`, and `README.md` exist and resolve at
  the root, every sub-catalog, and every collection. Each `AGENTS.md` is
  linked with `rel: "agents"` and each `README.md` with `rel: "describedby"`,
  both typed `text/markdown` and pointing at the raw file. Every catalog and
  collection declares the Portolan schema URI.
- **B** — All files exist and resolve, with scattered defects: a wrong media
  type on a `describedby` link, or a missing schema URI on some objects.
- **D** — A file class is absent across the catalog (every `AGENTS.md` 404s,
  or the links to them are missing), the schema URI appears nowhere, or
  hardcoded `self` links pin every object to one deployment URL.

## 2. Metadata integrity

- **A** — Every asset carries the registered media type for its format and
  `file:size`. Every collection lists a producer and exactly one host
  provider, the host reachable by URL or email. Licenses are valid SPDX
  identifiers, and mirrors carry `updated`. Checksums (`file:checksum`) are
  credited when present, and they are cheap to generate, but their absence
  does not cost a grade.
- **B** — Providers, licenses, and media types are in order, but `file:size`
  is missing on some assets or `updated` has gone stale.
- **D** — Provider lists are empty (so the catalog has no owner and no
  contact), a forbidden license value like `proprietary` appears, or most
  data assets carry an unregistered media type.

## 3. Cloud-native assets

- **A** — The primary data asset of every collection is cloud-native
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

- **A** — Every `AGENTS.md` is dataset-specific: it names join keys, shows
  runnable remote queries against published URLs, states the CRS with its
  practical consequences, documents quirks the schema cannot express, offers
  non-trivial query recipes, and points at related collections.
- **B** — Present and linked at every level, but thin: access snippets and a
  schema restatement without quirks, recipes, or cross-references.
- **D** — Boilerplate repeated across collections, or content that contradicts
  the machine metadata it describes.

## 5. Visualization

- **A** — Every geospatial collection has a thumbnail that resolves and was
  rendered from its default style, plus at least one style asset per render
  path with the default marked by a `default` role. The catalog as a whole offers
  three or more visualizations that express genuinely different aspects of the data —
  a categorical theme, a confidence surface, a density view — not three
  renderings of the same picture. The only exception is data that is truly
  just a geometry with an attribute or two that do not visualize; per the
  [styling guidance](styling.md).
- **B** — A resolving thumbnail and a single default style on every
  collection, nothing more.
- **D** — Geospatial collections missing a thumbnail or a style entirely, or
  thumbnail links that 404.

## 6. Performance and first render

A catalog is judged at its front door: paste the root URL into a STAC
browser, open a collection, and see whether data appears before the user
gives up.

- **A** — The default view of every collection renders visible data
  immediately at its natural full extent. Tiled visual assets carry content
  from zoom 0 (or the collection's full-extent zoom): sub-pixel features get
  generalized low-zoom overviews — dissolved coverage, density fills, or
  representative points — rather than relying on the tiler to drop what does
  not fit. Visual assets live in the same repository as the catalog that
  references them.
- **B** — Everything renders, but slowly or partially: heavyweight
  thumbnails, low-zoom tiles that are technically present but visually
  near-empty, a first paint that takes long enough to doubt.
- **D** — The default view is blank. A tileset whose minimum zoom starts
  levels below the full extent, with no fallback layer or extent hint, shows
  a user nothing until they already know where to look — the worst possible
  first impression, and indistinguishable from a broken catalog.

## 7. Maintenance signals

- **A** — `updated` is set and recent on every synced object, mirrors carry
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

## The A+ judgment

Everything above can be verified by inspection, and an honest A is a catalog
anyone can rely on. The A+ asks a different kind of question, drawn from the
[Candid Core Framework](https://lettersfromthreadedfoundry.substack.com/p/candid-core-framework):
does this catalog candidly outline known limitations, potential biases, and
inappropriate use cases to promote responsible data application? Not "is the
metadata complete", but is the dataset aware of its own blind spots — what
does it preserve, what does it erase, and does it say so? The grader assesses
this qualitatively, reading the catalog the way a prospective user would.

Marks of an A+ catalog:

- **Candid evaluation.** Suggested uses grounded in real applications;
  explicit inappropriate uses ("this is not a land-tenure product");
  quantified accuracy with uncertainty shipped as data, not just a headline
  number; named biases with mitigations; definitions stated and cited.
- **Narrative and context.** The README reads as a story with the links woven
  in — the source paper, the producing agency, the program behind the data —
  so a user leaves understanding not just the schema but the world the data
  describes.
- **An experience, not just an artifact.** Renders instantly, styled with
  care, escalating access examples that are runnable and genuinely
  interesting, documentation scoped correctly at every level of the tree.
- **Network participation.** The catalog is registered on the Portolan
  registry. A team can use excellent data internally and earn an A; the A+
  is reserved for catalogs contributing to the shared network.
- **Feedback loops.** The code that built the catalog is published, and a
  user who finds a mistake can file an issue or open a pull request against
  it. This practice is young and not yet expected, which is exactly why it
  distinguishes.

## The overall grade

A catalog's checkable grade is its weakest dimension, raised by at most one
step when most other dimensions sit at A. The floor rule is the point:
excellence in visible dimensions cannot buy back a broken machine contract,
because the consumers who depend on that contract never see the polish. The
A+ is then awarded, or not, on top of a clean A.
