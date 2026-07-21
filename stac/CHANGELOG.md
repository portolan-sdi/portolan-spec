# Changelog

All notable changes to the Portolan STAC profile will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Initial version of the Portolan STAC profile, moved from the
  `stac-portolan-extension` repository into `stac/`.
- JSON Schema covering the specification's schema-checkable structural
  requirements: non-empty titles and descriptions, titles on `child`/`item`
  links, no `self` links with relative typed structural links, `type`,
  `roles`, `file:size`, and `file:checksum` required on every asset,
  https-only absolute asset hrefs, `providers` with a producer and a
  reachable host, collection `license` never the deprecated `proprietary`,
  WGS84 bbox range validity, and the `rel: "agents"` link (with `type`) on
  Catalogs and Collections.
- Examples for a root catalog, a single-file vector collection, and a
  partitioned vector collection with an item.

### Changed

- No `portolan:`-prefixed fields are defined: the versioned schema URI in
  `stac_extensions` is the single signal of specification version, declared
  on catalogs and collections only (items inherit conformance).
