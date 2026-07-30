# Agent guidance, NAIP Colorado 2023

This collection holds NAIP Colorado 2023.
Read the item index `items.parquet` with DuckDB, then open a scene's image href through /vsicurl with rasterio. Do not download a scene, they are about 1.8 GB each.
For a quick preview use the thumbnail asset.
License is other. Attribute as NAIP imagery provided by USDA Farm Service Agency.
The original upstream source is https://planetarycomputer.microsoft.com/api/stac/v1/search?collections=naip&bbox=-106.6059,38.7455,-104.5917,40.4223&datetime=2023-01-01T00:00:00Z/2023-12-31T23:59:59Z&filter-lang=cql2-json&filter={"op":"=","args":[{"property":"naip:state"},"co"]}&limit=1000 , a live endpoint referenced by URL only.
