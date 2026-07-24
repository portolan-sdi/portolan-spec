# Best Practices — Catalog Philosophy

Core defines the shape of a catalog: the required
[structure](../portolan/core.md#core-structure) and the
[nesting rules](../portolan/core.md#nested-catalogs-flat-collections). This
page covers the judgment calls the spec leaves open: what one catalog should
contain, how to organize it, and what maintaining it actually involves.

## Scope by steward, not by theme

The most durable catalog boundaries follow data stewardship.
[Portolan NL](https://source.coop/cholmes/portolan-nl), a cloud-native mirror
of Dutch national geodata, organizes 21 collections as one sub-catalog per
producing institution: Kadaster, Rijkswaterstaat, CBS, and so on. Each
sub-catalog inherits one upstream, one license posture, and one contact point
from its institution, so provenance stays coherent without per-collection
bookkeeping. Themes shift with fashion. Stewardship rarely moves.

Within a steward's catalog, give each published dataset one collection. Keep
several data files inside a single collection when they share provenance and a
schema family. Portolan NL's administrative areas hold municipal, provincial,
and national boundaries as three GeoParquet assets in one collection rather
than three collections, because they are one dataset at three levels.

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
so choose them as contracts. Keep the source's own name for the id, lowercased,
and let the title carry the translation: Portolan NL uses Dutch ids like
`bestuurlijke_gebieden` under the English title "Administrative Areas
(Bestuurlijke Gebieden)", which keeps ids stable against upstream while titles
serve discovery. Keep tooling artifacts out of ids. An export prefix that
leaks from an ETL pipeline into a collection id is a temporary detail made
permanent.

## Maintenance is the product

Publishing a catalog is the cheap part. What separates a catalog people build
on from one they route around is everything that happens after:

- **Regenerate documentation from metadata on every publish.** Hand-edited
  pages drift: collection tables that link to renamed collections, feature
  counts that disagree between levels, examples that 404 after a layout
  change. Generated pages cannot.
- **Tend the invisible contract.** Checksums, providers, media types, the
  schema URI, and `updated` timestamps on mirrors are invisible in a browser
  and load-bearing for agents and validators. A catalog can look polished,
  with resolving thumbnails and rich prose, while failing every machine that
  reads it. Budget maintenance for both surfaces.
- **Record syncs.** A mirror that never updates `updated` gives consumers no
  way to judge freshness, which reads as abandonment even when the data is
  current.

## Catalogs worth studying

- [Portolan NL](https://browser.portolan-sdi.org/#/external/data.source.coop/cholmes/portolan-nl/catalog.json)
  — an institution-scoped national mirror with exceptional per-collection
  agent guides and thematic style variants.
- The [reference catalog](../../examples/) in this repo — small, fully
  conformant, and regenerated end-to-end from manifests.
