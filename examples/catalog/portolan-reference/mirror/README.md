# Mirrored Collections

Cloud-native mirror Collections of data maintained elsewhere.

## Collections

| Collection | Contents | Description |
|---|---|---|
| [San Francisco Addresses (EAS)](./san-francisco-addresses/README.md) | 5,000 points | A fixed 5,000-record extract of San Francisco's 388,550-record master address database, kept small on purpose for spec demonstration. |

## Where the Data Comes From

The Collection here is a mirror, so this catalog hosts a copy of data produced elsewhere.

San Francisco Addresses (EAS) tracks the [DataSF San Francisco Addresses with Units (GeoJSON, 5k extract)](https://data.sfgov.org/resource/ramy-di5m.geojson?$limit=5000&$order=:id), a live endpoint refetched on every build rather than pinned, licensed PDDL-1.0.
