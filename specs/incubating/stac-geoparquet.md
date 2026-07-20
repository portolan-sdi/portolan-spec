# Incubating — STAC-GeoParquet

**Status: maturing convention, may become required.**

For catalogs with many items (e.g. more than 100), include a
[stac-geoparquet](https://github.com/stac-utils/stac-geoparquet) file alongside
`collection.json` to enable search and filtering without a STAC API server.

This is a best practice while tooling matures and may become a requirement in a
later Portolan version. It is incubating rather than normative so that catalogs are
not held to it before the tooling and conventions (file location, naming, and how
it is linked from the collection) are settled.
