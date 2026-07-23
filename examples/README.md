# Examples

Working reference catalogs that exercise the spec end to end.

## Portolan Reference Catalog

[`catalog/reference/`](catalog/reference/) is a complete, v0.1-conformant
Portolan catalog built from real, openly licensed data pulled from its original
upstream sources. It is the canonical reference for what a valid Portolan catalog
looks like. When in doubt about how to structure a Catalog, a Collection, or an
Asset, look here.

It exercises every major case in the spec.

- Vector polygons and points, GeoParquet 2.0, from Natural Earth, the US Census
  Bureau, the City of Boston, PDOK Kadaster, and DataSF. The GeoParquet assets
  document their columns with the table extension and declare their CRS with
  the projection extension.
- A raster Collection, Cloud Optimized GeoTIFF with per-band statistics.
- A tabular, non-geospatial Collection, plain Parquet with documented columns.
- Nested Catalogs and flat Collections, official and mirror provenance,
  PMTiles visualizations, and data-driven MapLibre styles.
- Attributed Collections that carry the attribution extension.

Every Collection carries a cloud-native canonical data Asset and also cites its
true original upstream file as a `source`-role Asset, each with its own real
`file:size` and sha2-256 multihash `file:checksum`. Every node has a `README.md`
with runnable code for opening the data and an `AGENTS.md` with guidance for
agents.

### Regenerating it

The catalog is produced by the generator in [`tools/`](tools/) from the
manifests in [`manifests/`](manifests/). Each manifest file describes one whole
catalog and holds everything catalog-specific, so the generator itself carries
no per-catalog values. It reads every manifest in the directory and builds each
into `catalog/<manifest-stem>/`. It is a small set of plain modules under
`tools/` run through the [`build.py`](tools/build.py) entrypoint, which carries a
PEP 723 dependency header, so `uv` resolves its Python dependencies on the fly.

```bash
uv run examples/tools/build.py                              # build every manifest
uv run examples/tools/build.py --catalog reference          # one catalog
uv run examples/tools/build.py --only boundaries/us-counties   # one Collection
```

Prerequisites on your PATH, GDAL 3.x with the Parquet and COG drivers
(`ogr2ogr`, `ogrinfo`, `gdal_translate`, `gdalinfo`, `gdal_rasterize`,
`gdal_create`, `gdalwarp`), `tippecanoe`, and `uv`. The generator downloads each source once
into a git-ignored cache, converts it, computes real checksums, writes the STAC
tree with `AGENTS.md` and `README.md` beside every node, and validates the
result against
[`../stac/json-schema/v0.1.0/schema.json`](../stac/json-schema/v0.1.0/schema.json).

Thumbnails are drawn in Web Mercator at the data's true aspect ratio over a CARTO
light tile basemap, so previews read as maps rather than stretched squares. The
basemap is set once in the manifest `thumbnails` block, and each Collection's
`style` block drives both its thumbnail paint and its MapLibre styles, so the
preview mirrors the map. A `category_field` colours features by category, the
counties are coloured by state, for example.

A few upstream sources are live endpoints, the Boston export, the DataSF layer,
and the Eurostat API, so their `source` Asset checksums reflect the copy fetched
at build time. The other sources are version-stable.

### Note, planned CRS and engine changes

A design is approved to preserve the source CRS and drop the GDAL command-line
prerequisite. It is not implemented yet. The full design lives locally in
`docs/superpowers/specs/2026-07-23-preserve-source-crs-engine-swap-design.md`.
Until then the behavior below still describes the current generator. Reminders
for whoever implements it.

- Preserve the source CRS by default, for both vector and raster. Today the
  vector path force-reprojects every source to EPSG:4326. After the change the
  canonical Asset keeps its native CRS and `proj:code` is derived from the real
  output, never hardcoded. Two sources actually differ from 4326, `us-counties`
  is EPSG:4269 and `netherlands-provinces` is EPSG:28992, so they are the
  regression anchors that prove the source CRS survives.
- Make the output CRS configurable in the manifest with an optional `output_crs`
  field, global with a per-collection override. Absent, the source CRS is
  preserved. Present, the canonical Asset is reprojected to that CRS.
- Keep WGS84 and Web Mercator where the standard demands them. The STAC `bbox`
  stays in-range WGS84 because the schema requires it, the PMTiles feed stays
  lon/lat because tippecanoe only ingests that, and thumbnails stay Web Mercator
  EPSG:3857 for a consistent UI. None of these follow `output_crs`.
- The canonical vector write stays on `geoparquet-io` `optimize_for="web"`, which
  preserves the input CRS. Reconfirm that on a real EPSG:28992 source before
  wiring the rest of the vector path.
- Drop the GDAL CLI. The vector path moves to DuckDB spatial and the raster path
  to rasterio, both of which vendor their own GDAL in their wheels, so only
  `tippecanoe` and `uv` remain on the PATH.

The normative requirements are in [`specs/portolan/`](../specs/portolan/) and the
profile is in [`stac/`](../stac/).
