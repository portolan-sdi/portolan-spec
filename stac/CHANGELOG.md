# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Added

- Initial version of the Portolan extension.
- Field: `portolan:version`, required on Catalog, Collection, and Item.
- JSON Schema covering the specification's schema-checkable structural
  requirements: non-empty titles and descriptions, titles on `child`/`item`
  links, `type`, `roles`, `file:size`, and `file:checksum` required on every
  asset, https-only absolute asset hrefs, collection `license` never the
  deprecated `proprietary`, WGS84 bbox range validity, and the
  `rel: "agents"` link (with `type`) on Catalogs and Collections.
- Examples for a root catalog, a single-file vector collection, and a
  partitioned vector collection with an item.
