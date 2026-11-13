# MapLibre terrain example

A single-page map that reads one Portolan Collection asset, the terrarium-encoded
elevation PMTiles of GEM-15, and draws it three ways. It is the first example in
this repository that exercises elevation data rather than vector tiles.

The Collection is
[gem-15-catalog](https://source.coop/portolan-mirrors/gem-15-catalog), a Portolan
mirror of GEM-15, the Google Research near-global 15 m surface and terrain
elevation models described in
[doi:10.31223/X55N75](https://doi.org/10.31223/X55N75).

## What it shows

- A `raster-dem` source backed by PMTiles, read in the browser over HTTP range
  requests, with no tile server.
- A `color-relief` layer carrying an absolute hypsometric ramp, so colour means
  height in metres rather than a position in the local range.
- A `hillshade` layer over that tint, using the `igor` method, which is the
  method designed to sit under other layers.
- A toggle that raises MapLibre 3D terrain from the same source, with an
  exaggeration slider.
- A style switcher that loads the Collection's three published style assets
  straight off the object store, so a reader can see that a Portolan style
  document is complete and needs no rewriting by a client.
- Five preset views inside GEM-15 coverage, including the Kalgoorlie Super Pit,
  where the paper resolves the benches of a pit over 115 m deep.

GEM-15 is a surface model, so buildings and canopy are part of the terrain.
Elevations are metres above the EGM96 geoid. Coverage runs 84N to 61S and
excludes Russia, China, Mongolia and Greenland.

## How to run it

The page is self-contained and needs no build step. It does need to be served
over HTTP rather than opened from the filesystem, because it loads an ES module.

```bash
python -m http.server --directory examples/maplibre-terrain 8000
```

Then open `http://localhost:8000/` in a browser.

Both dependencies are pinned and come from unpkg. MapLibre GL JS 6.18.0 ships ES
modules only, so it is imported from a module script. The pmtiles 4.5.0 browser
build is an immediately invoked function that sets a global, so it loads from a
classic script tag. The `color-relief` layer type requires MapLibre GL JS 5.6.0
or newer, and the `hillshade-method` property requires 5.5.0 or newer.

## The data is not published yet

The gem-15-catalog Collection has not had its first data publish, so the terrain
PMTiles asset answers 404 today. The page checks for the asset on load and
raises an explanatory banner instead of showing an empty map. Nothing in the
page has to change when the data lands, because the published addresses are
fixed. Progress is tracked at
[portolan-mirrors/gem-15-catalog](https://github.com/portolan-mirrors/gem-15-catalog).

## What a Portolan raster-dem terrain layer is

A Portolan Collection publishes cloud-native bytes that a browser can read
directly. For elevation, that means a format MapLibre accepts as a `raster-dem`
source, which is a tiled image whose red, green and blue channels encode height.

GEM-15 itself is distributed as 26,970 Float32 Cloud Optimized GeoTIFFs. MapLibre
cannot read those as elevation, because a `raster-dem` source accepts only the
terrarium and Mapbox Terrain-RGB encodings. So the mirror derives one PMTiles
archive from the DSM in terrarium encoding, where
`elevation = (R * 256 + G + B / 256) - 32768`. The archive is a single file read
over range requests, global, 256 px tiles, zoom 0 to 13, which is about the
native 15 m resolution. MapLibre overzooms past 13 rather than requesting tiles
that do not exist.

Terrarium has no no-data value, so GEM-15 writes NaN and ocean alike as 0 m. The
hypsometric ramp therefore paints 0 m as a water tone, and that tone doubles as
the no-data tone. This matches how the AWS terrain tiles behave.

### Why this style uses absolute asset URLs

The vector styles in this repository reference their tiles with a relative path,
`pmtiles://../name.pmtiles`, resolved against the `styles/` directory that holds
them. That form depends on the client resolving it. The generator in
[`../tools/derivatives.py`](../tools/derivatives.py) says so: the path is the one
"clients like portolan-browser bind onto the data they loaded".

MapLibre GL JS does not resolve it. A source `url` is passed through to the
request unchanged, and the pmtiles protocol handler takes everything after
`pmtiles://` as the archive address and hands it to `fetch`. A relative path
there resolves against the HTML document, not against the style that declared it.
A style served from an object store and loaded into a page on another origin
would look for its tiles beside the page.

This example loads the Collection's styles directly into MapLibre, with no client
in between, so the styles it loads use absolute published URLs. That is a
decision about raster styles only. It does not change the relative convention for
vector styles, which existing clients already resolve.

## Raster styling is still an open question

Portolan's visualization style requirements are vector-only today. How a raster
style is expressed, and in particular how a continuous raster declares its colour
ramp, is unsettled. See
[`../../specs/incubating/raster-styling.md`](../../specs/incubating/raster-styling.md)
and the discussion in
[#41](https://github.com/portolan-sdi/portolan-spec/issues/41).

This example is evidence for that discussion rather than a proposal. It shows
what a working raster style looks like when it is written as a plain MapLibre
style document beside the data, and it shows two things the spec will have to
decide: where an absolute colour ramp is declared, and how a client learns the
encoding of an elevation asset. Neither is expressible in Portolan metadata now.

## Attribution

GEM-15 requires attribution. The data is produced by Google and licensed
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). The page carries
"This dataset is produced by Google | CC-BY-4.0" on the `raster-dem` source and
in the panel, and every published style asset carries the same string.
