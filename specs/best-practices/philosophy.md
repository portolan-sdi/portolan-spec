# Best Practices — Catalog Philosophy

Core defines the shape of a catalog: the required
[structure](../portolan/core.md#core-structure) and the
[nesting rules](../portolan/core.md#nested-catalogs-flat-collections). This
page covers the judgment calls the spec leaves open: what one catalog should
contain, how to organize it, and what maintaining it actually involves.

## Design for the person who shows up

A catalog is a data product, and the measure of a data product is what a
user can do with it ([Sundwall,
2025](https://radiant.earth/blog/2025/11/great-data-products/)). Every choice
below — scope, depth, naming, maintenance — serves one scenario: someone
arrives at your catalog knowing nothing, and within minutes they understand
what the data is, whether it fits their problem, and how to get it. The
README is that first landing point; the structure is what makes the second
minute as smooth as the first. Optimize for the visitor's experience, not
the publisher's convenience, and most of the judgment calls resolve
themselves.

## Scope by steward, not by theme

The most durable catalog boundaries follow data stewardship.
[Portolan NL](https://source.coop/cholmes/portolan-nl), a cloud-native mirror
of Dutch national geodata, organizes 21 collections as one sub-catalog per
producing institution: Kadaster, Rijkswaterstaat, CBS, and so on. Each
sub-catalog inherits one upstream, one license posture, and one contact point
from its institution, so provenance stays coherent without per-collection
bookkeeping. Themes shift with fashion. Stewardship rarely moves.

Within a steward's catalog, give each published dataset one collection. When
related datasets accumulate — boundaries at several administrative levels, a
product family with shared provenance — group their collections under a
sub-catalog rather than packing multiple datasets into one collection as
sibling assets. A collection whose assets are really three datasets makes
every consumer disambiguate them; a sub-catalog makes the grouping navigable.

## Shallow and uniform beats deep and clever

Portolan NL keeps every path the same length: root, institution, collection.
No collection sits deeper than another, so traversal is predictable and an
agent that has walked one branch has learned the whole catalog. Thematic
groupings ("water infrastructure", "boundaries") appear as tables in the
README, not as directory levels. Prose reorganizes for free. Directories are
forever. Add an intermediate catalog when a steward publishes enough
collections that a flat list stops being readable, not because a taxonomy
feels tidy.

## Names outlive everything

Collection ids become URLs, join targets, and lines in other people's scripts,
so choose them as contracts. Keep ids short, lowercase, and snake_case, and
let the title do the describing: an id like `administrative_areas` under the
title "Administrative Areas of the Netherlands (municipal, provincial,
national)" gives scripts a stable handle while the title serves discovery and
translation. Keep tooling artifacts out of ids. An export prefix that leaks
from an ETL pipeline into a collection id is a temporary detail made
permanent, and so is a pipeline stage name like `alpha/` baked into a
published path.

## Maintenance is the product

Publishing a catalog is the cheap part. What separates a catalog people build
on from one they route around is everything that happens after:

- **Regenerate documentation from metadata on every publish.** Hand-edited
  pages drift: collection tables that link to renamed collections, feature
  counts that disagree between levels, examples that 404 after a layout
  change. Generated pages cannot.
- **Tend the invisible contract.** Providers, media types, the schema URI,
  and `updated` timestamps on mirrors are invisible in a browser and
  load-bearing for agents and validators. A catalog can look polished, with
  resolving thumbnails and rich prose, while failing every machine that
  reads it. Budget maintenance for both surfaces.
- **Record syncs.** A mirror that never updates `updated` gives consumers no
  way to judge freshness, which reads as abandonment even when the data is
  current.

## Catalogs worth studying

Different data, different organizations, different concerns — browse them to
see the patterns before reading about them:

- [Portolan NL](https://browser.portolan-sdi.org/#/external/data.source.coop/cholmes/portolan-nl/catalog.json)
  — an institution-scoped national mirror with exceptional per-collection
  agent guides and thematic style variants.
- [Planet — Venezuela earthquake](https://source.coop/planet/venezuela-earthquake-2026-06-24)
  — an event-response imagery catalog: narrative README with the event story
  up front, escalating access recipes from a browser link to a
  whole-collection data cube, and pre-merged convenience mosaics so users
  need not juggle forty tiles.
- [Fields of the World — Global](https://source.coop/ftw/global-data)
  — a global ML-derived dataset: candid caveats ("not a land-tenure
  product"), per-polygon confidence with the derivation documented, quality
  layers shipped as sibling data, and the build code linked from the catalog
  itself.
- The [reference catalog](../../examples/) in this repo — small, fully
  conformant, and regenerated end-to-end from manifests.

This list should grow toward a handful of exemplars across data types and
publisher types. If you have built a catalog that teaches a pattern these do
not, propose it.

## This is a discussion

Nothing on this page is definitive. It is a working community's current best
understanding of how to make great data products, extracted from a small
number of real catalogs, and it will change as more people publish and
report back. If your experience contradicts a recommendation here, or your
catalog solved a problem this page does not cover, open an issue or a pull
request on the
[spec repository](https://github.com/portolan-sdi/portolan-spec) — the
guidance improves the same way the catalogs do.
