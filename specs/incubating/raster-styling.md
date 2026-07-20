# Incubating — Raster Styling

**Status: open, under discussion ([#41](https://github.com/portolan-sdi/portolan-spec/issues/41)).**

The [Visualization Styles](../portolan/core.md#visualization-styles) requirements in
core are **vector-only**: they describe MapLibre GL style files for PMTiles. How
raster styles are expressed is unspecified.

Open questions:

- **Colormaps** — how a continuous raster's color ramp is declared so a client can
  colorize it at draw time (e.g. via the STAC `render` extension and the required
  min/max statistics).
- **Legends** — how a categorical raster maps pixel values to labels and colors.
- **Continuous vs. categorical vs. multiband** — whether these need distinct style
  representations, and how a client tells them apart.

Until this is settled, a display-ready COG (embedded color table, or a continuous
raster colorized from its embedded min/max statistics) satisfies the "render from
source" path in core and needs no separate style file. This document will graduate
into `core.md` / `formats.md` once the expression is agreed.
