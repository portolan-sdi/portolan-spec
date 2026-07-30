# Examples

Working reference catalogs that exercise the spec end to end.

## Portolan Reference Catalog

[`catalog/portolan-reference/`](catalog/portolan-reference/) is a complete, v0.1-conformant
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
- A tabular, non-geospatial Collection, plain Parquet with documented columns
  and a runnable DuckDB example joining it to a geometry Collection, which the
  spec asks for whenever geometry and attributes live in separate files.
- Nested Catalogs and flat Collections, PMTiles visualizations, and data-driven
  MapLibre styles that load straight into MapLibre GL JS.
- Attributed Collections that carry the attribution extension.
- Both render paths, a PMTiles `visual` derivative on most vector Collections
  and render-from-source on the two small Natural Earth Collections.

Every Collection is a mirror. The spec derives that from who hosts the copy, and
an organization hosting data it did not produce is a mirror even when it is the
primary distributor. Portolan SDI serves every asset here and produced none of
the data, so there is no honest way to present one of these as official. No
Collection carries a `canonical` link either, because that is owed only when the
upstream publishes its own STAC, and none of these eight do.

Every Collection carries a cloud-native canonical data Asset with its own real
`file:size` and sha2-256 multihash `file:checksum`. The five whose upstream is a
directly downloadable file also cite that original as a `source`-role Asset. The
other three upstreams are live API endpoints, so they are referenced by URL only,
which the spec asks for and which keeps a checksum off bytes this catalog does
not control. Every node has a `README.md` with runnable code for opening the data
and an `AGENTS.md` with guidance for agents.

### Regenerating it

The catalog is produced by the generator in [`tools/`](tools/) from the
manifests in [`manifests/`](manifests/). Each manifest file describes one whole
catalog and holds everything catalog-specific, so the generator itself carries
no per-catalog values. It reads every manifest in the directory and builds each
into `catalog/<manifest-stem>/`. Each manifest is named after the `id` it
declares, so the manifest, the build directory, and the published prefix all
read the same. It is a small set of plain modules under
`tools/` run through the [`build.py`](tools/build.py) entrypoint, which carries a
PEP 723 dependency header, so `uv` resolves its Python dependencies on the fly.

```bash
uv run examples/tools/build.py                              # build every manifest
uv run examples/tools/build.py --catalog portolan-reference   # one catalog
uv run examples/tools/build.py --only boundaries/us-counties   # one Collection
```

Prerequisites on your PATH, `tippecanoe` and `uv`. The whole generator, vector
and raster conversion and thumbnails alike, runs on DuckDB spatial, rasterio,
and rio-cogeo, not the GDAL CLI, so no GDAL command-line install is needed.
The generator downloads each source once into a git-ignored cache, converts
it, computes real checksums, writes the STAC tree with `AGENTS.md` and
`README.md` beside every node, and validates the result with rashid, the
canonical Portolan validator.

Thumbnails are drawn in Web Mercator at the data's true aspect ratio over a CARTO
light tile basemap, so previews read as maps rather than stretched squares. The
basemap is set once in the manifest `thumbnails` block, and each Collection's
`style` block drives both its thumbnail paint and its MapLibre styles, so the
preview mirrors the map. A `category_field` colours features by category, the
counties are coloured by state, for example.

Three upstream sources are live endpoints, the Boston export, the DataSF layer,
and the Eurostat API. They are marked `stable: false` in the manifest and carry
no `source`-role Asset, because formats.md scopes that Asset to an original that
is directly downloadable rather than an API, and a checksum pinned to bytes this
catalog does not control is guaranteed to rot. Their READMEs say the upstream is
referenced by URL only. The other five sources are version-stable and do carry
the original.

A `stable: false` source is still refetched on every build rather than served
from the cache, because the canonical Asset is converted from those bytes and a
stale cached copy would publish data that no longer matches upstream. That is
what core.md asks for when it requires those values to be regenerated at publish
time.

### Revalidating it

The build validates what it just wrote.
[`check_catalogs.py`](tools/check_catalogs.py) revalidates the built tree,
with the data pass at full scope unless a baseline narrows it, so it refetches the
stable upstream sources and proves the `file:size` and `file:checksum` published
for each. That is the one check that
catches an upstream drifting away from a checksum this repo already published.
It reads the rashid pin out of `build.py`, so the validator that checks a catalog
is the validator that built it. Errors and warnings both fail, because a warning
in a reference example is a real defect.

```bash
uv run examples/tools/check_catalogs.py                      # every catalog
uv run examples/tools/check_catalogs.py --catalog portolan-reference  # one catalog
```

### Where it is published

A catalog that only exists in git proves the bytes are right and proves nothing
about how a client reads it, over HTTP range requests against a real object
store. So each catalog is also published to the Portolan repository on Source
Cooperative, where the reference catalog is readable at
<https://data.source.coop/portolan/portolan-pipeline/portolan-reference/main/>.

CI publishes on every push to `main` that changes a manifest, a generator module,
or a committed rebuild, since each changes the bytes a catalog is made of. A pull
request gets its own preview under `PRs/<number>/`, torn down when it closes, and
a comment linking it in [STAC Browser](https://browser.portolan-sdi.org/) so
review can open the catalog rather than read a diff of Parquet and COG.
Publishing by hand needs Source Cooperative credentials in the environment and
`s5cmd` on your PATH.

```bash
uv run examples/tools/publish_catalogs.py --list                        # publishable stems
uv run examples/tools/publish_catalogs.py --catalog portolan-reference --dry-run
uv run examples/tools/publish_catalogs.py --catalog portolan-reference
```

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

## NAIP Mosaic Mirror

`catalog/naip-mosaic/`, built from
[`manifests/naip-mosaic.yaml`](manifests/naip-mosaic.yaml), is the second
catalog, and unlike the reference catalog it is **not** fully conformant. That is the point of it. One
Collection publishes 924 National Agriculture Imagery Program scenes as per-scene
Items whose Cloud Optimized GeoTIFFs stay on the Microsoft Planetary Computer.

The difference from the reference catalog is custody, not provenance. This
Collection is a mirror by the same rule as the other eight, its producer and its
host differ. What is new is that it does not host the bytes it describes. 1.86 TB
of imagery lives upstream and is referenced by URL. `file:size` comes from a HEAD
on each object. `file:checksum` is omitted, because obtaining it honestly means
reading every scene and inventing it would be a false claim.

**`catalog/naip-mosaic/` is not committed, unlike the reference catalog.** It is
936 files of metadata the generator reproduces from that manifest in about
1 m 45 s, so `examples/.gitignore` excludes it and CI builds it fresh rather than
git carrying a snapshot. `publish-catalogs.yaml` builds it, gates it with
`check_catalogs.py`, and publishes it to Source Cooperative on every pull request
and on every push to main. Two things get worse for this catalog because of that.
The weekly `catalog-upstream.yaml` run only iterates the committed trees under
`examples/catalog/`, so it no longer covers `naip-mosaic` at all. And
`publish-catalogs.yaml` skips a pull request from a fork, since GitHub withholds
its secrets there, so a fork's pull request now gets no validation of this
catalog whatsoever, where the committed tree used to be at least readable in the
diff. What does not change, the publish workflow's path triggers still fire for
this catalog through `examples/manifests/**` and `examples/**/*.py`, only the
`examples/catalog/**` trigger has nothing left to match for it.

That leaves 2772 errors the generator cannot fix, so this catalog is gated against
an accepted-findings baseline in
[`expected-findings/naip-mosaic.json`](expected-findings/naip-mosaic.json) rather
than against zero. The baseline names each rule, why it fires, and where the
question is tracked. A rule it does not name still fails, and a named rule over its
ceiling still fails, so a real regression cannot hide behind a known gap. The
reference catalog has no baseline and stays at zero tolerance.

The baseline also narrows rashid's data scope to `local` for this catalog, since
the default pass streams every asset in full and 924 remote scenes is not a CI job.
That is a narrowing, not a skip. Every data rule still runs against the assets
inside the catalog tree, and only the remote hrefs are treated as unfetchable. See
[`tools/CLAUDE.md`](tools/CLAUDE.md) for how it works and what it still cannot
reach.

It is also the first Collection in the repo to carry a `canonical` link, since the
Planetary Computer publishes its own STAC and none of the reference catalog's eight
upstreams does. So it exercises a conditional MUST that had shipped untested.

`publish_catalogs.py --list` reports `naip-mosaic` as a publishable stem, so once
this work lands on `main` the catalog will publish to
`https://data.source.coop/portolan/portolan-pipeline/naip-mosaic/main/`. **That URL
is not live yet.**

The normative requirements are in [`specs/portolan/`](../specs/portolan/) and the
profile is in [`stac/`](../stac/).
