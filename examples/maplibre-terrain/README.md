# MapLibre terrain example

A single-page map that reads one Portolan Collection asset, the terrarium-encoded
elevation PMTiles of GEM-15, and draws it three ways. This is the first example
in this repository that uses elevation data.

The Collection is
[gem-15-catalog](https://source.coop/portolan-mirrors/gem-15-catalog), a Portolan
mirror of GEM-15. GEM-15 is the Google Research near-global 15 m surface and
terrain elevation model described in
[doi:10.31223/X55N75](https://doi.org/10.31223/X55N75).

## What it shows

- A `raster-dem` source backed by PMTiles, read in the browser over HTTP range
  requests, with no tile server.
- A `color-relief` layer with an absolute hypsometric ramp, so color means
  height in metres rather than a position in the local range.
- A `hillshade` layer over that tint, using the `igor` method, which is the
  method intended for a hillshade beneath another layer.
- A toggle that raises MapLibre 3D terrain from the same source, with an
  exaggeration slider.
- A style switcher that loads the three published style assets of the Collection
  from the object store. A reader can see that a Portolan style document
  is complete and needs no rewriting by a client.
- Preset views inside GEM-15 coverage, among them the Kalgoorlie Super Pit,
  where the paper resolves the benches of a pit over 115 m deep.

GEM-15 is a surface model, so buildings and canopy are part of the terrain.
Elevations are metres above the EGM96 geoid. Coverage runs 84N to 61S and
excludes Russia, China, Mongolia, and Greenland.

## How to run it

The page is self-contained and needs no build step. Serve it over HTTP rather
than opening it from the filesystem, because it loads an ES module.

```bash
python -m http.server --directory examples/maplibre-terrain 8000
```

Then open `http://localhost:8000/` in a browser.

The page pins both dependencies and loads them from unpkg. MapLibre GL JS 6.18.0
provides ES modules only, so a module script imports it. The pmtiles 4.5.0
browser build sets a global, so a classic script tag loads it. The
`color-relief` layer type requires MapLibre GL JS 5.6.0 or newer, and the
`hillshade-method` property requires 5.5.0 or newer.

## The data is not published yet

The gem-15-catalog Collection has not had its first data publish, so the terrain
PMTiles asset answers 404 today. The page checks for the asset on load and shows
an explanatory banner instead of an empty map. Nothing in the page changes when
the catalog publishes, because the published addresses stay the same. The
catalog repository is
[portolan-mirrors/gem-15-catalog](https://github.com/portolan-mirrors/gem-15-catalog).

## What a Portolan raster-dem terrain layer is

A Portolan Collection publishes cloud-native bytes that a browser can read
directly. For elevation, that means a format MapLibre accepts as a `raster-dem`
source. Such a source is a tiled image whose red, green, and blue channels encode
height.

Google distributes GEM-15 as 26,970 Float32 Cloud Optimized GeoTIFFs. MapLibre
cannot read those as elevation, because a `raster-dem` source accepts only the
terrarium and Mapbox Terrain-RGB encodings. So the mirror derives one PMTiles
archive from the DSM in terrarium encoding, where
`elevation = (R * 256 + G + B / 256) - 32768`. The archive is one file, read over
range requests, global, 256 px tiles, zoom 0 to 13. Zoom 13 is about the native
15 m resolution. MapLibre overzooms past 13 rather than requesting tiles that do
not exist.

Terrarium has no no-data value, so GEM-15 writes NaN and ocean alike as 0 m. The
hypsometric ramp paints 0 m as a water tone, and the same tone marks a cell with no data. The AWS terrain tiles behave the same way.

### Absolute asset URLs in a raster style

The vector styles in this repository reference their tiles with a relative path,
`pmtiles://../name.pmtiles`, resolved against the `styles/` directory that holds
them. That form depends on the client to resolve it. The generator in
[`../tools/derivatives.py`](../tools/derivatives.py) says so: the path is the one
"clients like portolan-browser bind onto the data they loaded".

MapLibre GL JS resolves nothing here. It passes a source `url` through to the
request unchanged, and the pmtiles protocol handler takes everything after
`pmtiles://` as the archive address and gives it to `fetch`. A relative path then
resolves against the HTML document rather than against the style that declared
it. A style served from an object store and loaded into a page on another origin
would look for its tiles beside the page.

This example loads the Collection styles into MapLibre, with no client
in between, so the styles it loads use absolute published URLs. That decision
covers raster styles only. The relative convention for vector styles stays as it
is, because existing clients already resolve it.

## Raster styling is still an open question

The visualization style requirements of Portolan are vector-only today. The spec
does not define how a raster style is expressed, nor how a continuous raster
declares its color ramp. See
<!-- vale ai-tells.GrowthMetaphors = NO -->
<!-- The rule matches the directory name in the path below, not prose. -->
[the raster styling document](../../specs/incubating/raster-styling.md)
<!-- vale ai-tells.GrowthMetaphors = YES -->
and the discussion in
[#41](https://github.com/portolan-sdi/portolan-spec/issues/41).

This example supplies evidence for that discussion. It proposes no rule. It
shows one raster style that works, written as a plain MapLibre style document
beside the data. It also shows two points the spec must
settle. The first point is where an absolute color ramp belongs. The second point
is where a client finds the encoding of an elevation asset. Portolan metadata
expresses neither one today.

## Attribution

GEM-15 requires attribution. Google produces the data and licenses it
[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/). The string "This
dataset is produced by Google | CC-BY-4.0" appears on the `raster-dem` source and
in the page panel. Each published style asset repeats the same string.
