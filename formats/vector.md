# Vector Data Format Requirements

## Required Formats

- **MUST** provide data in GeoParquet format
  - Follows [GeoParquet specification](https://geoparquet.org/)
  - Enables efficient querying and analysis without a server

## Recommended Formats

- **SHOULD** provide PMTiles for visualization
  - Optimized for web map rendering
  - Cloud-native, range-request friendly

## Styling

- **MAY** include `style.json` for default visualization
  - Compatible with MapLibre GL JS and deck.gl
  - See [best practices](../best-practices.md) for styling recommendations
