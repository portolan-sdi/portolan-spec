# Portolan specification

This folder is the normative Portolan specification. A catalog conforms to
Portolan when it meets the requirements in these files. The guidance in
[`specs/best-practices/`](../best-practices/) and the unfinished drafts in
[`specs/incubating/`](../incubating/) are not part of conformance.

## Contents

- [`core.md`](core.md) — the requirements that apply to every catalog,
  whatever its data format. It covers catalog structure, conformance,
  and versioning, collections, items, assets, and links.
- [`formats.md`](formats.md) — the requirements for each data format, such as
  GeoParquet, PMTiles, COG, and COPC.
- [`requirements.yaml`](requirements.yaml) — the manifest that gives each
  normative statement in the two documents a stable ID. Validators cite these
  IDs in their findings.

Read `core.md` first. Then read `formats.md` for each format that your catalog
publishes.
