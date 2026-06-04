# Tabular (Non-Geospatial) Data Format Requirements

> **Status: Proposal (RFC).** This addendum is additive and not yet normative. It
> proposes first-class support for **non-geospatial tabular datasets** in a Portolan
> catalog. Filed to start a discussion; open questions for the working group are at
> the bottom. Complements the [Git-Backed Catalog proposal (#20)](https://github.com/portolan-sdi/portolan-spec/pull/20).

## Motivation

An SDI federates open **data**, not just maps. Some of the most valuable public
datasets a publisher can share have **no geometry at all** — they are tables keyed by
time, by administrative code, or by category rather than by location. Examples:

- **National electricity-grid load** — a time-series of system load (MW) per timestamp
  (e.g. Fingrid open data).
- **Industrial electricity prices by country** — a table keyed by country code and
  half-year period (e.g. Eurostat `nrg_pc_205`).

These are clean, columnar Parquet datasets that belong in the same federated catalog as
the spatial layers — they are queried with the same engines (DuckDB, Arrow), versioned
the same way, and carry the same provenance requirements. Today the spec assumes every
dataset is geospatial, so there is no sanctioned way to publish them, and the CLI
rejects/ignores non-geospatial Parquet (see [extensions.md](../extensions.md), where
`.tsv`/`.xlsx` are listed under *Ignored Files* and `.parquet` is recognized only when
it carries geo metadata).

This addendum makes a non-geospatial table a first-class Portolan collection.

## What this proposes (additive)

A **tabular collection** is a STAC Collection whose primary `data` asset is a Parquet
file **with no geometry column** and no GeoParquet `geo` metadata. It is published
exactly like a single-file vector collection (see
[Collection-Level Assets](vector.md#collection-level-assets)) — same directory layout,
same versioning, same provenance — but it carries no spatial footprint.

### Marking a collection non-spatial

The collection **MUST** be explicitly flagged as non-spatial so that tools, validators,
and agents do not treat the missing footprint as an error or try to render it on a map.
We propose a boolean Portolan property:

```json
"portolan:geospatial": false
```

- When `portolan:geospatial` is `false`, the collection is a **tabular** dataset and the
  geometry/spatial-extent relaxations below apply.
- When the property is absent or `true`, the collection is geospatial and all existing
  format addenda (vector/raster/pointcloud) apply unchanged. This keeps the change fully
  backward-compatible: every existing catalog behaves exactly as before.

**Design choice — why a flag rather than reusing an existing STAC mechanism.** We
considered three alternatives and prefer the explicit flag:

1. *Infer from a null/empty `extent.spatial`.* STAC technically allows
   `extent.spatial.bbox` to be `[[ ]]` or a null-island placeholder, but "no bbox" is
   ambiguous — it can also mean "global", "unknown", or "not yet computed". An explicit
   flag distinguishes *intentionally non-spatial* from *spatial-but-unmeasured*, which a
   federation agent needs to know to route a query correctly.
2. *A media-type / `roles` signal on the asset.* The asset stays
   `application/vnd.apache.parquet` with `roles: ["data"]` in both cases, so it cannot
   carry the distinction on its own.
3. *The STAC Datacube or Table extension as the marker.* These describe **schema**, not
   spatiality, and we want the spatial/non-spatial decision to be a single, cheap,
   collection-level read. (The [Table extension](https://github.com/stac-extensions/table)
   remains **RECOMMENDED** alongside the flag to describe columns — see below.)

A single explicit boolean is the smallest, least ambiguous signal. The exact property
name is an open question (see below).

### Geometry and spatial extent

For a tabular collection (`portolan:geospatial: false`):

- The Parquet asset **MUST NOT** be required to contain a geometry column, and **MUST
  NOT** be expected to carry GeoParquet `geo` metadata.
- `geometry`/`bbox` (on any STAC Item) **MAY** be `null` or omitted.
- The Collection's `extent.spatial` **MAY** be omitted, or set to the STAC "unknown"
  placeholder `{"bbox": [[-180, -90, 180, 90]]}` only if a value is required by a
  downstream validator — but a non-spatial collection **SHOULD** omit it rather than
  assert a global footprint it does not have.
- The Collection's `extent.temporal` **SHOULD** still be populated when the table has a
  time dimension (most do), e.g. the first/last timestamp of a load time-series.

### Relaxing the core spatial implication

[core.md](../core.md) and the format addenda currently assume every dataset is
geospatial. Two spots need a relaxation for tabular collections:

1. **`core.md` → "STAC Compliance"** states a catalog *"MUST be a valid STAC Catalog or
   Collection"*. STAC's Collection schema makes `extent.spatial.bbox` **required**. We
   propose adding a sentence there (or here, normatively) that **for collections with
   `portolan:geospatial: false`, the spatial extent requirement is relaxed**: the
   collection MAY omit `extent.spatial`, and a Portolan validator MUST NOT reject a
   non-spatial collection for lacking a spatial footprint.
2. **`core.md` → "Format-Specific Requirements"** and
   [extensions.md](../extensions.md) currently route every dataset to the vector/raster/
   pointcloud addenda and treat non-geo Parquet as not importable. We propose listing
   **this addendum** there as the path for non-geospatial Parquet, and updating
   `extensions.md` so that a `.parquet` file *without* geo metadata is classified as a
   **tabular dataset** (importable) rather than ignored.

### Describing the schema (recommended)

Because a tabular dataset has no geometry to hint at its meaning, the schema carries all
the semantics. A tabular collection **SHOULD** describe its columns using the
[STAC Table extension](https://github.com/stac-extensions/table) (`table:columns`), so
that consumers and agents can discover column names, types, and descriptions without
opening the Parquet file:

```json
"table:columns": [
  {"name": "geo",       "type": "string", "description": "Country code (ISO-3166-1 alpha-2 / Eurostat)"},
  {"name": "period",    "type": "string", "description": "Reporting half-year, e.g. 2024-S1"},
  {"name": "price_eur_kwh", "type": "double", "description": "Industrial electricity price, EUR per kWh, incl. taxes"}
]
```

All other Portolan core requirements apply unchanged: absolute S3 asset hrefs, relative
STAC links, `providers`, the `rel: "via"` provenance link to the canonical source,
`README.md`, and `versions.json` version tracking.

## Example: `collection.json` for a tabular dataset

A non-geospatial collection holding industrial electricity prices by country (Eurostat):

```json
{
  "type": "Collection",
  "stac_version": "1.0.0",
  "id": "eurostat-electricity-prices",
  "title": "Industrial electricity prices by country",
  "description": "Half-yearly industrial electricity prices (EUR/kWh, including taxes) by European country. Non-geospatial tabular dataset. Source: Eurostat nrg_pc_205.",
  "license": "CC-BY-4.0",
  "portolan:geospatial": false,
  "stac_extensions": [
    "https://stac-extensions.github.io/table/v1.2.0/schema.json"
  ],
  "extent": {
    "temporal": {
      "interval": [["2007-01-01T00:00:00Z", "2024-12-31T23:59:59Z"]]
    }
  },
  "providers": [
    {
      "name": "Eurostat",
      "roles": ["producer", "licensor"],
      "url": "https://ec.europa.eu/eurostat"
    }
  ],
  "table:columns": [
    {"name": "geo", "type": "string", "description": "Country code (Eurostat / ISO-3166-1 alpha-2)"},
    {"name": "period", "type": "string", "description": "Reporting half-year, e.g. 2024-S1"},
    {"name": "price_eur_kwh", "type": "double", "description": "Industrial electricity price, EUR/kWh, including taxes"}
  ],
  "assets": {
    "data": {
      "href": "https://example-bucket.s3.eu-north-1.amazonaws.com/eurostat-electricity-prices/electricity-prices.parquet",
      "type": "application/vnd.apache.parquet",
      "roles": ["data"]
    }
  },
  "links": [
    {"rel": "root", "href": "../catalog.json", "type": "application/json"},
    {"rel": "parent", "href": "../catalog.json", "type": "application/json"},
    {"rel": "self", "href": "./collection.json", "type": "application/json"},
    {"rel": "version-history", "href": "./versions.json", "type": "application/json"},
    {
      "rel": "via",
      "href": "https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_205/default/table",
      "type": "text/html",
      "title": "Source: Eurostat — Electricity prices for non-household consumers"
    }
  ]
}
```

Note: there is no `extent.spatial`, no geometry, and no PMTiles derivative — none of
which apply to a non-spatial table.

## Open questions for the working group

1. **Property name and namespace.** Is `portolan:geospatial: false` the right signal, or
   should we instead use a positive `portolan:data_type: "tabular"` (vs `"vector"` /
   `"raster"` / `"pointcloud"`) so the data kind is always explicit for *every*
   collection? The latter is more uniform but touches existing collections.
2. **Schema description: required or recommended?** Should `table:columns` (STAC Table
   extension) be **MUST** for tabular collections — since the schema is the only
   semantic handle a consumer has — or remain **SHOULD** to keep the barrier to
   publishing low?
