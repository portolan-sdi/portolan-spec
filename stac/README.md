# Portolan STAC Profile

> **Work in Progress** — This profile is under active development. Requirement levels and the schema URL may change before the first stable release.

- **Title:** Portolan
- **Identifier:** <https://schema.portolan-sdi.org/v0.1.0/schema.json>
- **Field Name Prefix:** portolan (reserved; no fields defined in v0.1)
- **Scope:** Catalog, Collection — Items inherit conformance from their collection
- **[Extension Maturity Classification](https://github.com/radiantearth/stac-spec/tree/master/extensions#extension-maturity):** Proposal

A [Portolan](https://github.com/portolan-sdi) catalog is a directory of STAC metadata and cloud-native geospatial data, served from plain object storage and consumable with zero infrastructure. Following the approach of the [CEOS-ARD extension](https://github.com/stac-extensions/ceos-ard), this directory is both a **minimal extension** — a JSON Schema for the structural requirements checkable from STAC JSON alone — and a **profile**: how the [Portolan specification](../specs/portolan/) uses STAC and existing extensions, which link relations, media types, and roles it requires, and where full validation happens.

Declaring this extension is a claim of conformance, not proof of it: an object conforms only by passing the Portolan validator (see [Validation](#validation)).

## Fields

This extension defines **no fields**. The versioned schema URI declared in `stac_extensions` is the single signal of specification version; no separate version property exists (spec: Conformance and Versioning). Dataset versioning uses the [version extension](https://github.com/stac-extensions/version), never `portolan:` fields.

Declaration happens at the catalog and collection level only — every catalog and collection MUST declare the schema URI in `stac_extensions`; items inherit conformance from their collection and do not declare it. All objects within a catalog SHOULD declare the same URI; a validator flags a mismatch with the root catalog as a warning, not an error — a mixed-version catalog remains valid.

The `portolan:` prefix stays reserved for future use.

## What the schema enforces

The schema encodes the specification's structural requirements that STAC core leaves optional:

- Every Catalog and Collection has a non-empty `title` and `description`; every `child` and `item` link carries a `title` (spec: Human-Readable Titles).
- No object carries a `self` link, and structural links (`root`, `parent`, `child`, `item`, `collection`) are relative and carry `type: "application/json"` (`application/geo+json` for links to items), keeping a catalog fully portable (spec: Links).
- Every asset has `href`, a media `type`, at least one `role`, and `file:size` + `file:checksum` (spec: Assets). The checksum's multihash encoding is verified by tooling, not schema.
- Absolute asset hrefs use `https` — `s3://` and other bucket schemes are rejected; relative hrefs are allowed (spec: Assets).
- Every Collection declares `providers` with at least one `producer` and a `host` reachable through `url` or `email`; that the host is exactly one and listed last is checked by tooling (spec: Providers).
- Collection `license` is never the deprecated `proprietary`; SPDX validity and the `rel: "license"` link required with `other` are checked by tooling (spec: License).
- Every `bbox` — collection extent and item — contains only in-range WGS84 coordinates, with no sentinel "effectively infinite" values (spec: Bounding Boxes and Spatial Extent).
- Every Catalog and Collection links its `AGENTS.md` with `rel: "agents"` and `type: "text/markdown"` (spec: AGENTS.md).
- Every Catalog and Collection links its `README.md` with `rel: "describedby"` and `type: "text/markdown"` (spec: README.md).

## STAC Extensions

Portolan reuses established extensions rather than re-encoding the same information under `portolan:`. This table is the **normative registry** of the extensions the profile uses — the requirement level, the condition under which it applies, and the exact schema URI to pin in `stac_extensions`. The specification defers to this table rather than restating it.

Requirement keywords per BCP 14; a conditional MUST applies only when its condition holds.

| Name                | Schema URI for `stac_extensions`                                            | Requirement | When / Usage |
| ------------------- | --------------------------------------------------------------------------- | ----------- | ------------ |
| [Portolan][] | `https://schema.portolan-sdi.org/v0.1.0/schema.json` | **MUST**    | Always — every catalog and collection; items inherit conformance |
| [File Info][] | `https://stac-extensions.github.io/file/v2.1.0/schema.json`                 | **MUST**    | Every object with assets: `file:size` + `file:checksum` (multihash) on each asset |
| [Web Map Links][] | `https://stac-extensions.github.io/web-map-links/v1.3.0/schema.json`        | **MUST**    | When PMTiles are provided: the `rel: "pmtiles"` link |
| [Version][] | `https://stac-extensions.github.io/version/v1.2.0/schema.json`              | **MUST**    | When dataset versioning is used (never `portolan:` fields) |
| [Raster][] | `https://stac-extensions.github.io/raster/v2.0.0/schema.json`               | **MUST**    | When band-level detail is provided |
| [Vector][] | `https://stac-extensions.github.io/vector/v0.1.0/schema.json`               | **MUST**    | When layer-level detail is provided |
| [Table][] | `https://stac-extensions.github.io/table/v1.2.0/schema.json`                | SHOULD      | Tabular collections: document columns with `table:columns` |
| [Alternate Assets][] | `https://stac-extensions.github.io/alternate-assets/v1.2.0/schema.json`     | SHOULD      | Expose `s3://` alternates for absolute `https` asset hrefs |
| [Render][] | `https://stac-extensions.github.io/render/v2.0.0/schema.json`               | SHOULD      | Continuous rasters rendering from source (draw-time colorization) |
| [Projection][] | `https://stac-extensions.github.io/projection/v2.0.0/schema.json`           | MAY         | CRS / projection of the data |
| [Scientific][] | `https://stac-extensions.github.io/scientific/v1.0.0/schema.json`           | MAY         | Citation / DOI |
| [Contacts][] | `https://stac-extensions.github.io/contacts/v0.1.1/schema.json`             | MAY         | Richer contact info; never replaces url-or-email on the host provider |
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

Objects MUST NOT include a `self` link, and all structural links MUST be relative (pystac `SELF_CONTAINED` convention), so a catalog can be moved or rehosted without rewriting any file.

| `rel` | Where | Notes |
| ----- | ----- | ----- |
| `root`, `parent` | All objects (root catalog has no `parent`) | Relative; `type: "application/json"` |
| `child` / `item` | Catalogs and collections, one per child | Relative, typed (`application/geo+json` for items); MUST carry a `title` |
| `collection` | Items | Relative; `type: "application/json"` |
| `agents` | Catalog, Collection | Points to `AGENTS.md`, `type: "text/markdown"` |
| `describedby` | Catalog, Collection | Points to `README.md`, `type: "text/markdown"` |
| `via` | Collection | Mirror only: the original source, `type: "text/html"` |
| `canonical` | Collection | Mirror only: the source's own STAC root, MUST when the source publishes STAC |
| `license` | Collection | License text, MUST when `license` is `other` |
| `pmtiles` | Collection | Per web-map-links v1.3.0, with `pmtiles:layers`, when PMTiles are provided |

Whether a catalog is official or a mirror is derived from its providers (producer = host means official); a mirror records each sync in the core `updated` field. Every link in a catalog MUST resolve — a link that 404s is a conformance failure. This is a crawling check, outside JSON Schema.

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

Styles are STAC assets: each style file is a collection-level asset with `roles: ["style"]`, discovered by filtering assets on that role — no separate manifest exists (spec: Visualization Styles).

### Formats

Every collection and item is available in a cloud-optimized format; full requirements live in the specification's format sections, and the data-file internals are validated by tooling, not schema:

- **Vector** — GeoParquet 1.1/2.0 (compression, spatial ordering, row-group statistics); a PMTiles visualization derivative SHOULD be provided, registered through the `rel: "pmtiles"` link (an asset only when also intended for distribution), with MapLibre styles as `style` assets.
- **Raster** — COG with embedded per-band GDAL statistics in the leading header block.
- **Tabular (non-geospatial)** — Parquet as a collection-level asset, columns documented with the table extension, spatial requirements relaxed. No marker property: a tabular collection is identified by its data, a Parquet asset with no geometry column.
- **Point cloud** — reserved; COPC, pending a reference implementation.

## Validation

Per the specification, validation runs in separable passes:

1. **Structural** — STAC 1.1.0 core schemas.
2. **Metadata** — every requirement checkable from metadata alone. This profile's schema is the machine-checkable core of this pass; link resolution needs a crawler.
3. **Data** — requirements that need asset bytes (GeoParquet spatial ordering, row-group statistics, embedded COG statistics). Run by `portolan check`, MAY run independently.

Hosting requirements (HTTP Range support, CORS on all metadata and asset files) are properties of the server, validated by probe.

## Open questions

Tracked in the specification and deliberately **not** settled by this schema:

1. **Raster styling** — how raster styles are expressed (colormaps, legends, continuous vs. categorical vs. multiband) is under discussion in [`specs/incubating/raster-styling.md`](../specs/incubating/raster-styling.md); the MapLibre style requirements are vector-only for now.

## Examples

- [Root catalog](examples/catalog.json)
- [Single-file vector collection](examples/vector-collection.json) — GeoParquet + PMTiles + style + thumbnail as collection-level assets
- [Partitioned vector collection](examples/vector-partitioned-collection.json) and [partition item](examples/vector-partitioned-item.json)

The files are stored flat in `examples/` for convenience, but their relative hrefs describe the specification's canonical directory layout (`{collection_id}/collection.json`, `{item_id}/item.json` beneath it) — so href targets such as `../catalog.json`, `AGENTS.md`, and the data files are illustrative and not present in this repository. Per the spec's Links section the examples carry no `self` links and use only relative structural hrefs.

## Building and Testing

Every published schema version is tracked in this repository under `json-schema/v<version>/schema.json`; the `version` field in `package.json` names the current one and is the single source of truth. The publish workflow deploys the site from that tree.

From `stac/`:

```bash
npm install
npm test
```

`npm test` runs:

- **check-markdown** — remark lint over the profile documents.
- **check-version** — every versioned Portolan schema URI reference (schema `$id`, READMEs, examples, spec documents) matches the `package.json` version, and the matching `json-schema/v<version>/` directory exists.
- **check-examples** — [stac-node-validator](https://github.com/stac-utils/stac-node-validator) validates the examples, applying the schema where `stac_extensions` declares it.
- **check-portolan** — validates every example directly against the schema with ajv, the way the Portolan validator does. This is what exercises the schema's item rules — items never declare the schema URI, so `check-examples` alone would never apply it to them. It also verifies the examples' `file:checksum` values are well-formed sha2-256 multihashes, which the schema deliberately delegates to tooling.

## Contributing

This profile is maintained by the [Portolan SDI](https://github.com/portolan-sdi) project. Issues and pull requests are welcome.

## License

Apache-2.0
