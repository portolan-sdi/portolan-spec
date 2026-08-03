# Agent Guidance, Portolan Reference Catalog

Eight small Collections, each with its own AGENTS.md worth reading before
querying it. Two attribute joins connect them. The Eurostat electricity
prices table joins Natural Earth countries on ISO_A2_EH after remapping
Eurostat's EL to GR and UK to GB. Natural Earth populated places join
Natural Earth countries on ADM0_A3 after remapping SSD to SDS for South
Sudan. Everything else connects only spatially, and the boundary layers
differ hugely in scale, from 1:110m world polygons to Boston parcels, so
match scales before spatial joins.

- Natural Earth Countries (1:110m), 177 polygons, guide at ./reference/natural-earth-countries/AGENTS.md
- Natural Earth Populated Places (1:50m), 1,251 points, guide at ./reference/natural-earth-populated-places/AGENTS.md
- United States Counties (2023, 1:500k), 3,235 polygons, guide at ./boundaries/us-counties/AGENTS.md
- Boston Open Space, 1,012 polygons, guide at ./boundaries/boston-open-space/AGENTS.md
- Netherlands Provinces, 12 polygons, guide at ./boundaries/netherlands-provinces/AGENTS.md
- San Francisco Addresses (EAS), 5,000 points, guide at ./mirror/san-francisco-addresses/AGENTS.md
- Sample Raster COG, 3-band raster, guide at ./raster/sample-cog/AGENTS.md
- Eurostat Electricity Prices for Household Consumers, 65,412 rows, guide at ./tabular/eurostat-electricity-prices/AGENTS.md
