# NAIP Colorado 2023

The 924 National Agriculture Imagery Program scenes covering a Colorado study area flown between August and October 2023, at 0.3 m ground sample distance in UTM zone 13N. Each scene is a four-band Cloud Optimized GeoTIFF of red, green, blue and near infrared, hosted by the Microsoft Planetary Computer and referenced here by URL. The Collection publishes a stac-geoparquet item mirror and a compact bbox index so a client can load every footprint in one request.

License, other. Attribution, NAIP imagery provided by USDA Farm Service Agency.
Providers, USDA Farm Service Agency (producer, licensor), Esri (processor), Microsoft (processor), Portolan SDI (host).
Original source, https://planetarycomputer.microsoft.com/api/stac/v1/search?collections=naip&bbox=-106.6059,38.7455,-104.5917,40.4223&datetime=2023-01-01T00:00:00Z/2023-12-31T23:59:59Z&filter-lang=cql2-json&filter={"op":"=","args":[{"property":"naip:state"},"co"]}&limit=1000 .
Scenes, 924.
Scene bytes, hosted upstream and referenced by URL, not copied here.
Cloud-native asset, items.parquet (stac-geoparquet item mirror).
Note, scene assets carry file:size but no file:checksum, because this catalog does not host those bytes and cannot regenerate a digest at publish time. See NAIP-MIRROR-FOLLOWUP.md.
Note, the upstream source is a live endpoint, so it is referenced by URL only and not archived as a source asset.

## Open the data

This Collection describes scenes it does not host. Each Item carries its Cloud Optimized GeoTIFF as an item-level asset, and the asset href points at the upstream host. Read the whole item index in one query with DuckDB.

```sql
INSTALL spatial; LOAD spatial;
SELECT id, bbox, assets FROM read_parquet('items.parquet') LIMIT 5;
```

Then read any single scene straight from the upstream host, over range requests, without downloading it.

```python
import rasterio

href = "<the image asset href from an Item>"
with rasterio.open(f"/vsicurl/{href}") as src:
    print(src.profile, src.overviews(1))
```
