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

Prerequisites on your PATH, `tippecanoe` and `uv`. The whole generator, vector
and raster conversion and thumbnails alike, runs on DuckDB spatial, rasterio,
and rio-cogeo, not the GDAL CLI, so no GDAL command-line install is needed.
The generator downloads each source once into a git-ignored cache, converts
it, computes real checksums, writes the STAC tree with `AGENTS.md` and
`README.md` beside every node, and validates the result with reis, the
canonical Portolan validator.

Thumbnails are drawn in Web Mercator at the data's true aspect ratio over a CARTO
light tile basemap, so previews read as maps rather than stretched squares. The
basemap is set once in the manifest `thumbnails` block, and each Collection's
`style` block drives both its thumbnail paint and its MapLibre styles, so the
preview mirrors the map. A `category_field` colours features by category, the
counties are coloured by state, for example.

A few upstream sources are live endpoints, the Boston export, the DataSF layer,
and the Eurostat API, so their `source` Asset checksums reflect the copy fetched
at build time. The other sources are version-stable. Because a live endpoint's
bytes drift, a source marked `stable: false` is refetched on every build rather
than served from the cache, so its declared `file:size` and `file:checksum`
always describe the bytes the endpoint returned during that build. That is what
core.md asks for when it requires those values to be regenerated at publish time.

### Note, CRS and engine changes

The design to preserve the source CRS and move the data path off the GDAL
command line is implemented. The full design lives locally in
`docs/superpowers/specs/2026-07-23-preserve-source-crs-engine-swap-design.md`.

Done.

- Source CRS is preserved by default, for both vector and raster. The
  canonical Asset keeps its native CRS and `proj:code` is derived from the
  real output, never hardcoded. `us-counties` is EPSG:4269 and
  `netherlands-provinces` is EPSG:28992, so they are the regression anchors
  that prove the source CRS survives.
- The output CRS is configurable in the manifest with an optional `output_crs`
  field, global with a per-collection override. Absent, the source CRS is
  preserved. Present, the canonical Asset is reprojected to that CRS.
- WGS84 and Web Mercator stay where the standard demands them. The STAC `bbox`
  stays in-range WGS84 because the schema requires it, the PMTiles feed stays
  lon/lat because tippecanoe only ingests that, and thumbnails stay Web
  Mercator EPSG:3857 for a consistent UI. None of these follow `output_crs`.
- The GDAL CLI is gone from the data path. The vector path runs on DuckDB
  spatial and the raster path on rasterio, both of which vendor their own GDAL
  in their wheels.
- The GDAL CLI is gone from the thumbnail path too. `tiles.py` fetches and
  mosaics the XYZ basemap into a numpy canvas, DuckDB spatial reprojects and
  clips the vector to Web Mercator, rasterio warps the raster overlay on, and
  Pillow writes the PNG.
- The reference generator no longer requires the GDAL command-line tools at
  all. `tippecanoe` and `uv` are the only prerequisites on PATH now.

The normative requirements are in [`specs/portolan/`](../specs/portolan/) and the
profile is in [`stac/`](../stac/).
