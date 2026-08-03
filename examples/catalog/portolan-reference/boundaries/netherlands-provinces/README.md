# Netherlands Provinces

The 12 provinces of the Netherlands, administrative boundaries from the Dutch national spatial data infrastructure PDOK, derived from the Kadaster BRK Bestuurlijke Gebieden. Republished as cloud-native GeoParquet with a PMTiles visualization and categorical, labeled MapLibre styles.

[Kadaster](https://www.kadaster.nl), the Dutch cadastral agency,
derives the country's administrative division from the cadastral
registration and publishes it through
[PDOK](https://www.pdok.nl/introductie/-/article/bestuurlijke-gebieden),
the national open geodata platform, in an edition established every
January when municipal reorganizations take effect. This Collection
carries the 12 provinces of the 2026 edition, valid from January 1,
2026. PDOK names the layer as the base of public applications from
[atlasleefomgeving.nl](https://www.atlasleefomgeving.nl) to the
official bathing water site [zwemwater.nl](https://www.zwemwater.nl).

The geometry checks out against the national statistics office.
Computing `ST_Area` per province reproduces the official CBS surface
figures to one decimal, Utrecht 1,560.1 square kilometres against the
published 1,560.05.

Agents, [AGENTS.md](./AGENTS.md) has the CBS join recipe, the Baarle
enclave surprise, and the metric CRS consequences.

## Quick Start

```python
import geopandas as gpd

gdf = gpd.read_parquet("netherlands-provinces.parquet")
print(gdf.head())
```

The `data` asset is GeoParquet 2.0 with a native geometry type and a covering bbox column, so it needs a GeoPandas built on pyarrow 24 or newer. DuckDB spatial queries the same file in place, see [AGENTS.md](./AGENTS.md) for those patterns. Paths are relative to this directory, and the same code works against the published URL.

## Machine-Readable Metadata

Beside the data sits `iso19115.xml`, the upstream ISO 19115 metadata
record for BRK Bestuurlijke Gebieden, mirrored on July 31, 2026 from
the [Nationaal Georegister](https://www.nationaalgeoregister.nl/geonetwork/srv/dut/catalog.search#/metadata/208bc283-7c66-4ce7-8ad3-1cf3e8933fb5)
and carried as a metadata-role asset. Catalogs that already maintain
ISO metadata can ship it alongside the STAC this way instead of
abandoning it.

## Schema

| Column | Type | Description |
|---|---|---|
| `identificatie` | varchar | Province identifier PV20 through PV31, PV plus the CBS province code. The join key to CBS StatLine regional tables. |
| `naam` | varchar | Official province name. Fryslân carries its official Frisian spelling, a filter on Friesland returns nothing. |
| `code` | varchar | Two-digit CBS province code as a string, 20 through 31. Joins to ligt_in_provincie_code in the source's municipality layer. |
| `ligt_in_land_code` | varchar | Country code, the constant 6030 for Nederland. |
| `ligt_in_land_naam` | varchar | Country name, the constant Nederland. |
| `geom` | geometry('epsg:28992') | Province geometry, multipolygon, in the Dutch national grid EPSG:28992 in meters. |
| `bbox` | struct(xmin double, ymin double, xmax double, ymax double) | Per-feature bounding box struct in RD New meters, the GeoParquet covering. |

The table has 8 columns in all. The full list with types lives in `table:columns` on the `data` asset.

## Join the National Statistics

`identificatie` holds the CBS region codes PV20 through PV31, the same
keys every provincial table on
[CBS StatLine](https://opendata.cbs.nl) uses, which connects these 12
polygons to Dutch official statistics on population, income, land use,
and more. Trim the CBS side first, the classic OData API pads its keys
with trailing spaces.

## Water Is Inside the Boundaries

The provinces sum to 41,543 square kilometres while the land surface
of the Netherlands is about 33,500. Administrative boundaries divide
the Wadden Sea, the IJsselmeer, and the delta waters among provinces,
so Fryslân is the largest province by total area and roughly 42
percent water. Rankings and densities computed from these polygons
answer the water-inclusive question unless you subtract water first,
CBS publishes the land-only figures.

## Limitations

One annual snapshot, valid for January 1, 2026 only, and boundary
history needs the matching year's edition, PDOK keeps five. Derived
from the cadastre but not a substitute for it, parcel-level legal
questions belong to the BRK itself. The Caribbean Netherlands,
Bonaire, Sint Eustatius, and Saba, belongs to no province and is not
here.

## Provenance and License

License, CC-BY-4.0. Attribution, Kadaster / PDOK.
Providers, Kadaster (producer, licensor), PDOK (processor), Portolan SDI (host).
Original source, https://service.pdok.nl/kadaster/brk-bestuurlijke-gebieden/atom/downloads/BestuurlijkeGebieden_2026.gpkg .
Features, 12. Cloud-native asset, netherlands-provinces.parquet (GeoParquet 2.0).
