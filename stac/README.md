# Portolan Extension

> **Work in Progress** — This extension is under active development. Field names, requirement levels, and the extension URL may change before the first stable release.

- **Title:** Portolan
- **Identifier:** <https://portolan-sdi.github.io/portolan-spec/portolan/v0.1.0/schema.json>
- **Field Name Prefix:** portolan
- **Scope:** Catalog, Collection, Item
- **[Extension Maturity Classification](https://github.com/radiantearth/stac-spec/tree/master/extensions#extension-maturity):** Proposal

A [Portolan](https://github.com/portolan-sdi) catalog is a directory of STAC metadata and cloud-native geospatial data, served from plain object storage and consumable with zero infrastructure. Following the approach of the [CEOS-ARD extension](https://github.com/stac-extensions/ceos-ard), this repository is both a **minimal extension** — one field, `portolan:version`, plus a JSON Schema for the structural requirements checkable from STAC JSON alone — and a **profile**: how the Portolan specification uses STAC and existing extensions, which link relations, media types, and roles it requires, and where full validation happens.

Declaring this extension is a claim of conformance, not proof of it: an object conforms only by passing the Portolan validator (see [Validation](#validation)).

## Fields

| Field Name       | Type   | Description |
| ---------------- | ------ | ----------- |
| portolan:version | string | **REQUIRED.** The Portolan specification version the object was authored against (`0.1.0` for this schema), set to the same version as the declared schema URI, so tools can filter by specification version without resolving URIs. This is the *specification* version — dataset versioning uses the [version extension](https://github.com/stac-extensions/version). |

On Catalogs and Collections the field sits at the top level; on Items it sits in `properties`. All objects within a catalog SHOULD declare the same `portolan:version`; a validator flags a mismatch with the root catalog as a warning, not an error — a mixed-version catalog remains valid.

Other `portolan:`-prefixed fields are under discussion in the specification (e.g. the tabular marker, style manifests) and are intentionally neither validated nor rejected by this schema until settled — see [Open questions](#open-questions).

## What the schema enforces

Beyond `portolan:version`, the schema encodes the specification's structural requirements that STAC core leaves optional:

- Every Catalog and Collection has a non-empty `title` and `description`; every `child` and `item` link carries a `title` (spec: Human-Readable Titles).
- Every asset has `href`, a media `type`, at least one `role`, and `file:size` + `file:checksum` (spec: Assets). The checksum's multihash encoding is verified by tooling, not schema.
- Absolute asset hrefs use `https` — `s3://` and other bucket schemes are rejected; relative hrefs are allowed (spec: Assets).
- Collection `license` is never the deprecated `proprietary`; SPDX validity and the `rel: "license"` link required with `other` are checked by tooling (spec: License).
- Every `bbox` — collection extent and item — contains only in-range WGS84 coordinates, with no sentinel "effectively infinite" values (spec: Bounding Boxes and Spatial Extent).
- Every Catalog and Collection links its `AGENTS.md` with `rel: "agents"` and `type: "text/markdown"` (spec: AGENTS.md).

## STAC Extensions

Portolan reuses established extensions rather than re-encoding the same information under `portolan:`. This table is the **normative registry** of the extensions the profile uses — the requirement level, the condition under which it applies, and the exact schema URI to pin in `stac_extensions`. The specification defers to this table rather than restating it.

Requirement keywords per BCP 14; a conditional MUST applies only when its condition holds.

| Name                | Schema URI for `stac_extensions`                                            | Requirement | When / Usage |
| ------------------- | --------------------------------------------------------------------------- | ----------- | ------------ |
| [Portolan][] | `https://portolan-sdi.github.io/portolan-spec/portolan/v0.1.0/schema.json` | **MUST**    | Always — every catalog, collection, and item |
| [File Info][] | `https://stac-extensions.github.io/file/v2.1.0/schema.json`                 | **MUST**    | Every object with assets: `file:size` + `file:checksum` (multihash) on each asset |
| [Web Map Links][] | `https://stac-extensions.github.io/web-map-links/v1.3.0/schema.json`        | **MUST**    | When a PMTiles asset is present: the `rel: "pmtiles"` link |
| [Version][] | `https://stac-extensions.github.io/version/v1.2.0/schema.json`              | **MUST**    | When dataset versioning is used (never `portolan:` fields) |
| [Raster][] | `https://stac-extensions.github.io/raster/v2.0.0/schema.json`               | **MUST**    | When band-level detail is provided |
| [Vector][] | `https://stac-extensions.github.io/vector/v0.1.0/schema.json`               | **MUST**    | When layer-level detail is provided |
| [Table][] | `https://stac-extensions.github.io/table/v1.2.0/schema.json`                | SHOULD      | Tabular collections: document columns with `table:columns` |
| [Alternate Assets][] | `https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json`     | SHOULD      | Expose `s3://` alternates for absolute `https` asset hrefs |
| [Render][] | `https://stac-extensions.github.io/render/v2.0.0/schema.json`               | SHOULD      | Continuous rasters rendering from source (draw-time colorization) |
| [Projection][] | `https://stac-extensions.github.io/projection/v2.0.0/schema.json`           | MAY         | CRS / projection of the data |
| [Scientific][] | `https://stac-extensions.github.io/scientific/v1.0.0/schema.json`           | MAY         | Citation / DOI |
| [Contacts][] | `https://stac-extensions.github.io/contacts/v0.1.1/schema.json`             | MAY         | Responsible parties |
| [Attribution][] | `https://stac-extensions.github.io/attribution/v0.1.0/schema.json`          | MAY         | Display attribution |
| [Themes][] | `https://stac-extensions.github.io/themes/v1.0.0/schema.json`               | MAY         | Thematic classification |

Note that `item_assets` needs no extension — it is a core field in STAC 1.1.

As the profile grows, per-format requirement sets (vector, raster, tabular) may split into separate subprofile documents, as CEOS-ARD does for optical and SAR.

[Portolan]: https://github.com/portolan-sdi/portolan-spec
[File Info]: https://github.com/stac-extensions/file
[Web Map Links]: https://github.com/stac-extensions/web-map-links
[Version]: https://github.com/stac-extensions/version
[Raster]: https://github.com/stac-extensions/raster
[Vector]: https://github.com/stac-extensions/vector
[Table]: https://github.com/stac-extensions/table
[Projection]: https://github.com/stac-extensions/projection
[Alternate Assets]: https://github.com/stac-extensions/alternate-assets
[Render]: https://github.com/stac-extensions/render
[Scientific]: https://github.com/stac-extensions/scientific
[Contacts]: https://github.com/stac-extensions/contacts
[Attribution]: https://github.com/stac-extensions/attribution
[Themes]: https://github.com/stac-extensions/themes

## Profile

### Link relations

| `rel` | Where | Notes |
| ----- | ----- | ----- |
| `root`, `self`, `parent` | All objects (root catalog has no `parent`) | Structural links carry `type: "application/json"` (`application/geo+json` for links to items) |
| `child` / `item` | Catalogs and collections, one per child | MUST carry a `title` |
| `collection` | Items | — |
| `agents` | Catalog, Collection | Points to `AGENTS.md`, `type: "text/markdown"` |
| `via` | Collection | Original canonical source when data is mirrored, `type: "text/html"` |
| `canonical` | Collection | Mirror only: the source's own STAC root, MUST when the source publishes STAC |
| `license` | Collection | License text, MUST when `license` is `other` |
| `pmtiles` | Collection | Per web-map-links v1.3.0, with `pmtiles:layers`, when a PMTiles asset is present |

Every link in a catalog MUST resolve — a link that 404s is a conformance failure. This is a crawling check, outside JSON Schema.

### Media types and roles

| Format | Media type | Typical role |
| ------ | ---------- | ------------ |
| GeoParquet / Parquet | `application/vnd.apache.parquet` | `data` |
| COG | `image/tiff; application=geotiff; profile=cloud-optimized` | `data` |
| PMTiles | `application/vnd.pmtiles` | `visual` |
| COPC | `application/vnd.laszip+copc` | `data` |
| Thumbnail | `image/png` or `image/jpeg` | `thumbnail` |
| Sidecar metadata | (format-specific) | `metadata`, `iso-19115` |
| MapLibre style | `application/vnd.mapbox.style+json` | `style` (Portolan-defined role) |

### Formats

Every collection and item is available in a cloud-optimized format; full requirements live in the specification's format sections, and the data-file internals are validated by tooling, not schema:

- **Vector** — GeoParquet 1.1/2.0 (compression, spatial ordering, row-group statistics), paired with a PMTiles visualization derivative and MapLibre styles.
- **Raster** — COG with embedded per-band GDAL statistics in the leading header block.
- **Tabular (non-geospatial)** — Parquet as a collection-level asset, columns documented with the table extension, spatial requirements relaxed.
- **Point cloud** — reserved; COPC, pending a reference implementation.

## Validation

Per the specification, validation runs in separable passes:

1. **Structural** — STAC 1.1.0 core schemas.
2. **Metadata** — every requirement checkable from metadata alone. This extension's schema is the machine-checkable core of this pass; link resolution needs a crawler.
3. **Data** — requirements that need asset bytes (GeoParquet spatial ordering, row-group statistics, embedded COG statistics). Run by `portolan check`, MAY run independently.

Hosting requirements (HTTP Range support, CORS on all metadata and asset files) are properties of the server, validated by probe.

## Open questions

Tracked in the specification and deliberately **not** settled by this repository; the schema neither validates nor rejects the affected fields:

1. **The `portolan:version` property itself** — whether the duplicate property stays, or the versioned schema URI in `stac_extensions` becomes the single version signal. The schema currently requires the property, following the spec's Conformance and Versioning section; if it is removed, the extension remains valid STAC with no fields at all — the declared URI is then the only conformance and version claim (CEOS-ARD style).
2. **Tabular marker** — explicit `portolan:geospatial: false` vs deriving non-spatial status from the data.
3. **Styles as assets vs links** — and, downstream, whether a `portolan:styles` manifest is needed. The examples here show styles as assets with `roles: ["style"]`, illustrating one candidate; pending this ruling, they deliberately omit the `portolan:styles` manifest that the spec's PMTiles section currently mandates.
4. **Relative vs absolute structural links** — note STAC 1.1 core already requires `self` hrefs to be absolute; the examples use relative structural links with an absolute `self`.

## Examples

- [Root catalog](examples/catalog.json)
- [Single-file vector collection](examples/vector-collection.json) — GeoParquet + PMTiles + style + thumbnail as collection-level assets
- [Partitioned vector collection](examples/vector-partitioned-collection.json) and [partition item](examples/vector-partitioned-item.json)

The files are stored flat in `examples/` for convenience, but their relative hrefs describe the specification's canonical directory layout (`{collection_id}/collection.json`, `{item_id}/item.json` beneath it) — so href targets such as `../catalog.json`, `AGENTS.md`, and the data files are illustrative and not present in this repository.

## Building and Testing

This repository uses [stac-node-validator](https://github.com/stac-utils/stac-node-validator) to validate examples against the schema:

```bash
npm install
npm test
```

## Contributing

This extension is maintained by the [Portolan SDI](https://github.com/portolan-sdi) project. Issues and pull requests are welcome.

## License

Apache-2.0
