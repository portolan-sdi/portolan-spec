# Portolan Specification — Core

*The keywords MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT,
RECOMMENDED, MAY, and OPTIONAL in this document are to be interpreted as
described in BCP 14 [RFC 2119] [RFC 8174] when, and only when, they appear in all
capitals, as shown here.*

This document defines the requirements that apply to every Portolan catalog,
regardless of data format. Format-specific requirements live in
[`formats.md`](formats.md).

## Introduction

The goal of Portolan is to make it easier and cheaper for data providers to publish
their data, and to make that data more accessible to both humans and agents. If
Portolan is successful then all the world's spatial data will be much easier to
query and utilize in decisions that affect all of our lives.

The center of Portolan is the [SpatioTemporal Asset Catalog](https://stacspec.org/) 
specification - every Portolan implementation is a STAC catalog, and can be used 
with any STAC tooling. But where STAC can be used with any data format and can 
be implemented as an API or files on cloud storage, Portolan requires well-formed 
cloud-native formats, stored as files on browser-accessible online services. All
Portolan implementaions are [static catalogs](https://github.com/radiantearth/stac-spec/blob/master/best-practices.md#static-catalogs)
- there is no 'Portolan API' like the STAC API, as many of the key benefits of Portolan,
like scalability and lower cost, are achieved by the full embrace of cloud-native geospatial.

Portolan further requires that all catalogs follow the best practices to guide
AI agents to make use of them. Today that means adding an agents.md file to every
catalog and collection and building up a set of 
['skills'](https://github.com/portolan-sdi/portolan-skills) that guide agents to
make use of the cloud-native formats. In the future this will likely evolve as
the general best practices for agents continue to advance.

The specification aims to standardize the minimum requirements for a 'great' catalog,
and to provide guidance to go beyond that. But really the hope is that everyone 
goes well beyond the minimum and tries to make each catalog better than before. The 
aspiration of the authors of the specification is to build a real community of
collaborators who are all working together to build great data catalogs and share
tools and best practices so all can benefit.

## Core Structure

A Portolan catalog is a directory of STAC metadata and cloud-native geospatial
data. It MUST be a valid STAC catalog following STAC 1.1.0, with a root
`catalog.json` always required, even for a single collection.

A catalog is a tree of catalogs, collections, items, and assets: catalogs and
collections are internal nodes, items are leaves, and assets (data files) MUST sit
at the collection or item level. Catalogs organize only and MAY nest into
sub-catalogs; collections MUST be one level deep, containing only items or assets,
never nested collections. Every catalog and sub-catalog MUST contain a
`catalog.json`, an `AGENTS.md`, and a `README.md`; every collection MUST contain a
`collection.json`, an `AGENTS.md`, and a `README.md`.

A catalog has two entry points: `catalog.json` for machines (required at the root)
and `README.md` for humans. It is fully navigable; every catalog, collection, and
item links to the rest, so any object is reachable from any other (see
[Links](#links)).

```
project/
├── catalog.json
├── AGENTS.md
├── README.md
└── {collection_id}/
    ├── collection.json
    ├── AGENTS.md
    ├── README.md
    └── {item_id}/
        └── data.parquet
```

## Conformance and Versioning

A Portolan object declares conformance through the Portolan STAC extension, whose
versioned schema URI carries the specification version the object was authored
against.

Every catalog and collection MUST declare the versioned Portolan schema URI (e.g.
`https://schemas.portolan-sdi.org/portolan/v0.1.0/schema.json`) in its `stac_extensions`
array. The schema URI is the single signal of specification version; no separate
version property is defined. Declaration happens at the catalog and collection
level only, since assets cannot carry `stac_extensions`, and items inherit
conformance from their collection.

The specification version MUST NOT be conflated with the dataset version. Dataset
versioning, where used, MUST use the STAC [version
extension](https://github.com/stac-extensions/version).

All objects within a catalog SHOULD declare the same Portolan schema URI. A
validator MUST flag any catalog or collection whose declared URI differs from the
root catalog's; such a mismatch is a warning, not an error, and a mixed-version
catalog remains valid.

Declaring the Portolan extension is a claim of conformance, not proof of it. An
object conforms to this specification only by passing the Portolan validator.
Validation runs in separable passes:

- **Structural validation** against the STAC 1.1.0 schemas.
- **Portolan metadata validation**, covering every requirement checkable from
  metadata alone.
- **Portolan data validation**, covering requirements that require reading asset
  bytes, such as GeoParquet spatial ordering, row-group statistics, and embedded
  COG statistics.

The metadata passes MUST be executable without reading asset data; the data pass
MAY be run independently.

Portolan schemas are published at `schemas.portolan-sdi.org`. `versions.json` is a tooling
artifact and is NOT REQUIRED in a catalog for v0.1.

## Recommended STAC Extensions

Consistent with the reuse-first approach, Portolan datasets use established STAC
extensions wherever they apply rather than re-encoding the same information in
`portolan`. Which extensions are required versus recommended, the exact schema
URIs and versions to pin, and their usage are defined normatively by the Portolan
STAC Profile (see [`stac/`](../../stac/)), not restated here.

## Catalogs

The canonical entrypoint is a STAC `catalog.json` in the catalog root, which MUST
be valid. Catalogs MAY use nested sub-catalogs for organization but MUST NOT use
nested collections.

## Collections

Each collection lives in a subdirectory named with its collection ID. For a nested
collection the ID is a POSIX path (e.g. `environment/air-quality`) and the
directory sits under one or more intermediate catalog directories (see [Nested
Catalogs, Flat Collections](#nested-catalogs-flat-collections)). A collection
directory MUST contain a `collection.json` and holds one subdirectory per item.
Collection IDs SHOULD contain only lowercase letters, numbers, hyphens, and
underscores, start with a letter, and be unique within the catalog.

### Single-File Collections

When a collection holds a single data file (e.g. one GeoParquet file), that data
MUST be represented as a collection-level asset — no item directory or item JSON
is needed (see [Vector](formats.md#vector)). Alongside the `collection.json` and
the `.parquet`, such a collection may optionally carry a `.pmtiles`, a
`thumbnail.png`, and a `styles/` directory.

### Raster Collections

A collection holding multiple raster scenes MUST model each scene as an item
carrying its COG as an item-level asset; scene COGs MUST NOT be listed as
collection-level assets. Per-scene items are what let each scene carry its own
footprint and acquisition time, which a flat asset list cannot express. A
collection holding a single COG follows the single-file rule above: it MUST
expose that COG as a collection-level asset with no item directory (see
[Raster](formats.md#raster)).

## Nested Catalogs, Flat Collections

Portolan organizes hierarchy with nested catalogs, not nested collections:
intermediate levels are catalogs (`catalog.json`) and collections are always
leaves. A collection MUST NOT contain a child collection. This keeps collections
flat for STAC API compatibility while still allowing thematic organization above
them. A nested collection's ID is its POSIX path from the catalog root (e.g.
`environment/air-quality`); `portolan add` writes a `catalog.json` at each
intermediate level and links parent to child down to the leaf `collection.json`.

In directory terms, the root holds the root `catalog.json`, a level above a
collection holds an intermediate (thematic) `catalog.json`, a data directory holds
the leaf `collection.json`, and a subdirectory within a collection may hold a
`catalog.json` that organizes many items. Deep nesting is allowed, with every
level above the leaf a catalog; a catalog may also appear below a collection to
organize its items (for example, a raster collection grouping items by year).

```
environment/
├── catalog.json              ← intermediate catalog
├── air-quality/
│   ├── collection.json       ← leaf collection (data)
│   └── pm25.parquet
└── water-quality/
    ├── collection.json       ← leaf collection (data)
    └── turbidity.parquet
```

A `collection.json` with a child collection subdirectory beneath it is invalid.

## Items

Most collections represent their data as one or more STAC items, each with its own
metadata and assets. Portolan adds nothing to the STAC 1.1 Item beyond core: an
item MUST be a valid STAC item, carrying an `id`, a `geometry` and `bbox` (or null
geometry for non-spatial data), a `datetime` or a `start_datetime`/`end_datetime`
interval, its assets, and the structural links defined under [Links](#links).
The `datetime` clause restates STAC 1.1 core validity and is enforced by
structural validation; the Portolan-level guidance to carry an explicit
`datetime` lives under [Temporal Metadata](#temporal-metadata) as a SHOULD.
Item-level detail that other extensions already cover — file, raster, vector —
MUST use those extensions rather than being re-specified here.

Items are not always required. A single-file collection has none: its data is a
collection-level asset (see [Single-File Collections](#single-file-collections)).
A partitioned collection MAY represent each partition as an item, but this is not
required — see [Partitioned Collections](formats.md#partitioned-collections) for
when it is worthwhile. An ordinary collection with multiple distinct data files represents
each as an item.

## Assets

Every asset MUST include an `href`, the URI to the data, with relative or absolute
both allowed for now. Where an asset `href` is absolute, it MUST use `https`
rather than `s3`, since browsers cannot fetch `s3` URLs directly. An asset SHOULD
also provide `s3` or other cloud-native URLs through the
[alternate](https://github.com/stac-extensions/alternate-assets) extension, so
tools that prefer direct bucket access can use them. Portolan additionally
requires a `type`, meaning the media type, and at least one role on every asset.
STAC leaves both optional, but a validator and a browser cannot do their jobs
without them, so Portolan makes them mandatory. The `title` and `description`
fields are optional but recommended.

The required media type for each core format is:

| Format | Media type |
|--------|------------|
| GeoParquet and plain Parquet | `application/vnd.apache.parquet` |
| COG | `image/tiff; application=geotiff; profile=cloud-optimized` |
| PMTiles | `application/vnd.pmtiles` |
| COPC | `application/vnd.laszip+copc` |
| Thumbnail | `image/png` or `image/jpeg` |

Roles describe what each asset is for. Portolan uses the standard STAC role names
wherever they fit and requires at least one per asset: `data` for the primary
GeoParquet, COG, or Parquet; `visual` for the PMTiles rendering derivative;
`thumbnail` for the preview image; `metadata` for sidecar metadata, with
`iso-19115` used specifically for an ISO 19115 file. Multiple roles on one asset
are fine — use all that apply. The `style` role, used for MapLibre style files, is
a Portolan-defined role rather than a standard STAC one (see [Visualization
Styles](#visualization-styles)).

Portolan reuses existing extensions rather than restating their fields: `file` for
`file:values`, `table` for schema and columns, `raster` and `vector` for band and
layer detail, `license` for per-asset license, and `scientific` for citation or
DOI. Assets MUST carry `file:size` and `file:checksum` from the [file
extension](https://github.com/stac-extensions/file). The checksum MUST use
multihash encoding, not a raw sha256 string. These embedded values MUST be
regenerated at publish time, in the same operation that uploads the files, so they
always match what is in the bucket.

**Primary-vs-alternate.** A non-cloud-native representation MAY be included as an
alternate asset as long as an equivalent cloud-native primary asset exists (e.g. a
GeoJSON alongside the required GeoParquet). The cloud-native asset is the primary;
the rest are alternates.

## Links

Every catalog, collection, and item MUST include the structural links that make
the tree navigable: a catalog or collection MUST include `root` and `parent` links
(except the root catalog, which has no parent) and a `child` or `item` link for
every object it contains; an item MUST include `root`, `parent`, and `collection`
links. Every structural link MUST carry a `type` of `application/json` (or
`application/geo+json` for links to items).

All structural links MUST be relative, and objects MUST NOT include a `self` link.
This keeps a catalog fully portable: it can be created, validated, moved between
local, staging, and production environments, or rehosted at a new URL without
rewriting any file. This choice follows pystac's `SELF_CONTAINED` convention and
may be revisited in a future version if absolute self links prove necessary for
published catalogs.

Every link in a catalog MUST resolve. A validator MUST resolve each relative link
against the catalog's own file tree, whether on a local filesystem or on object
storage, and confirm the referenced file is present and is the correct object,
rather than merely checking that the `href` is present or well-formed. A link that
fails to resolve, or resolves to the wrong object, is a conformance failure.

Provenance (`via`) links are covered under [Source Provenance](#source-provenance).

## Human-Readable Titles

STAC Browser and other clients render `child` and `item` link titles directly;
without them a client must fetch every child just to display its name. Portolan
therefore requires human-readable titles throughout: every `catalog.json` and
`collection.json` MUST have a non-empty `title` and `description`; titles MUST be
human-readable, so a raw slug (`snake_case`) or a technical namespace prefix
(`ns:LayerName`) is not acceptable; and every `child` and `item` link MUST include
a `title`. A validator checks readability heuristically; it MUST flag a title that
fails the check, and because heuristics misfire, the finding is a warning, not an
error.

## Bounding Boxes and Spatial Extent

Bounding boxes carry the spatial footprint that drives extent unions and map-UI
browsing, and garbage coordinates poison the catalog-level extent and break
viewers. So every `bbox` — catalog extent, collection extent, and item — MUST:

- contain no `NaN` or infinite values (including 3D elevation coordinates);
- contain no sentinel "effectively infinite" values (e.g. `±1.79e308`);
- use only WGS84 coordinates in range (longitude -180 to 180, latitude -90 to 90)
  with south ≤ north; and
- in a 3D bbox, order the vertical axis with minimum elevation ≤ maximum
  elevation.

STAC requires `extent.spatial.bbox` for collections; for tabular (non-geospatial)
collections it represents the area of interest the data pertains to, not a
geometric footprint (see [Tabular](formats.md#tabular-non-geospatial)).

## Temporal Metadata

Items SHOULD carry an explicit `datetime` (or a `start_datetime` /
`end_datetime` interval) describing when the data applies.

## Data Storage

Cloud-native formats depend on clients fetching only the bytes they need, so
Portolan catalogs assume data is hosted in cloud object storage reachable over
HTTP range requests (S3-compatible or otherwise). Servers MUST support range
requests: honor the `Range` header, return `206 Partial Content`, and advertise
`Accept-Ranges: bytes`; HEAD requests MUST return an accurate `Content-Length`.
Servers MUST support HTTP/1.1 or greater; HTTP/2 or /3 is RECOMMENDED. Endpoints
that compress or transform responses in ways that break range semantics are not
conformant.

To let browser clients read data directly, servers MUST also enable CORS on all
metadata and asset files: `Access-Control-Allow-Origin: *` (or an equivalent
read-permitting policy), allowed methods including `GET` and `HEAD`, allowed
request headers including `Range`, and exposed response headers including
`Content-Range`, `Content-Length`, `Accept-Ranges`, and `ETag` (via
`Access-Control-Expose-Headers`).

## Providers

Every collection MUST identify the parties responsible for its data through the
STAC `providers` field. The list MUST include at least one provider with the
`producer` role, the organization that originally captured or created the data,
and exactly one provider with the `host` role, listed as the last element. The
host is the organization responsible for operating and maintaining this copy of
the catalog and its data, not the underlying cloud vendor whose storage it happens
to sit on; a catalog on S3 maintained by a city GIS office lists the office as
host, not AWS. Providers with the `processor` and `licensor` roles SHOULD be
included where they apply. A single organization MAY hold multiple roles; a
self-published dataset will typically list one provider as both producer and host.
Catalogs MAY also declare providers, but the collection-level declaration is
authoritative.

The host provider MUST include contact information: a `url` pointing to a page
where the maintainer can be reached, or an `email` field with a maintainer
address. `email` is not a core STAC field but is a valid extension of the provider
object, and the Portolan schema enforces that at least one of the two is present.
This is the maintainer-contact requirement for every Portolan catalog; a catalog
whose host provides neither is non-conformant. A collection MAY additionally use
the [contacts](https://github.com/stac-extensions/contacts) extension for richer
contact information, but doing so does not replace the url-or-email requirement on
the host provider.

## Source Provenance

Often a Portolan catalog is a mirror that complements an official source with
cloud-native formats rather than being the source itself, and users need to trace
back to the original. Every Portolan catalog is therefore one of two kinds:

- **Official** — published by the originating authority for the data. The catalog
  is a canonical home for the data, not a copy of one.
- **Mirror** — a cloud-native copy that complements a source maintained elsewhere.
  The mirror exists to add open formats, better access, or discoverability; the
  authoritative copy lives at the source.

Which kind a catalog is, is derived from its providers, not declared through any
dedicated property. A catalog is official when its producer and host are the same
organization; it is a mirror when they differ. An organization hosting data it did
not produce is a mirror under this definition even when it is the primary
distributor; the `via` link then simply records where the data originated.

A mirror MUST include a `via` link (type `text/html`) pointing to the original
source. When that source publishes its own STAC catalog, the mirror MUST also
include a `canonical` link pointing to the source's STAC, so consumers and agents
can follow the chain to the authoritative metadata, not just a landing page.
Whether the source publishes a STAC catalog cannot be determined from the mirror's
metadata alone, so a validator MAY surface a mirror without a `canonical` link as
informational, never as a failure. The
`via` and `canonical` links MAY both be present and point at different targets (a
human page and a STAC root). An official catalog carries no `via` or `canonical`
link to an upstream source, because it is the source.

A mirror MUST record when it was last synced from its source by setting the
top-level `updated` field (RFC 3339) at each synced catalog and collection to the
time of the sync. A sync is a metadata update, so this reuses the core STAC field
with no Portolan-specific addition; a consumer judges the freshness of a copy by
comparing `updated` against the source. Sync cadence and richer source-freshness
metadata are deferred to a future version.

## License

Every collection MUST declare a `license` in its `collection.json`. The value MUST
be an SPDX license identifier (e.g. `CC-BY-4.0`, `Apache-2.0`), or the STAC value
`other` when no SPDX identifier fits, in which case the collection MUST include a
license link (`rel: license`) pointing to the license text. The deprecated STAC
1.1 value `proprietary` MUST NOT be used. A collection whose data is genuinely
restricted still declares its license explicitly rather than omitting it.

## AGENTS.md

Every catalog and collection MUST include an `AGENTS.md` in Markdown, referenced in
the STAC `links` array (`rel: "agents"`, `type: text/markdown`). It is a link, not
an asset — it describes the data, it is not the data. Beyond existing and being
linked, its content is open-ended; the aim is to help agents use the data well,
covering access patterns (base URLs, S3 paths, code examples), useful aggregations
and queries, data-quality notes, related collections, and schema or
coordinate-system conventions — anything non-obvious. See
[best-practices](../best-practices/) for guidance on what makes a good `AGENTS.md`.

## README.md

Every catalog and collection MUST have a `README.md` in Markdown, referenced in the
STAC `links` array (`rel: "describedby"`, `type: text/markdown`). Like `AGENTS.md` it
is a link, not an asset — it describes the data, it is not the data. `describedby` is
the IANA-registered relation for a resource carrying a description of the linked
resource, and is already common in STAC. The `README.md` MUST contain at minimum a
title, description, license, and data provenance.

## Metadata

Collections SHOULD include machine-readable metadata (e.g. [Apache
Ossie](https://ossie.apache.org/)) when they have many coded or categorical
variables or complex classification schemes, and SHOULD include column
descriptions, which will likely become a requirement as tooling matures.

## Visualization

Every geospatial collection MUST provide a way to render its data with zero
infrastructure, either by:

- **rendering from source** — the data asset is small and simple enough for
  clients to draw directly (e.g. a small GeoParquet, or a COG that is already
  display-ready, whether through an embedded color table or as a continuous raster
  colorized at draw time via the render extension and the required min/max
  statistics); or
- **a visualization derivative** — an additional cloud-native product optimized
  for rendering, published as a collection-level asset with `roles: ["visual"]`;
  PMTiles is the recommended vector format today.

A consumer decides by inspection: use a `visual` asset if present, otherwise render
from source. Non-geospatial collections are exempt. Whether an asset is small and
simple enough to render from source is not decidable from metadata, so a validator
cannot enforce this requirement directly; it MAY advise, as informational, when a
large vector collection lacks a `visual` derivative. Collections MUST include a
thumbnail generated from default styling and MUST provide visualization styles as
standalone STAC assets appropriate to the render path, except where the render path
is self-rendering (a display-ready COG or a small GeoParquet drawn directly), which
needs no separate style file.

### Visualization Styles

When a collection provides a render path it MUST provide at least one style telling
clients how to draw it, in a format appropriate to that render path. Style files are
STAC assets: each style MUST be registered as a collection-level asset with `roles:
["style"]`, alongside the data and thumbnail. A client or agent discovers a
collection's styles by filtering assets on that role, so no separate manifest is
needed and this specification defines none. Because STAC assets are an unordered
JSON object, the default style is identified by a reserved asset key rather than by
position: when a collection provides more than one style, exactly one style asset
MUST use the key `style-default`. The remaining styles use descriptive
`style-<variant>` keys such as `style-labeled`, and every style carries a
human-readable name in its `title`.

The concrete style format is defined per data format in [`formats.md`](formats.md):
for vector (PMTiles) it is a MapLibre GL style file, while raster styling is still
under discussion (see
[`specs/incubating/raster-styling.md`](../incubating/raster-styling.md)).
