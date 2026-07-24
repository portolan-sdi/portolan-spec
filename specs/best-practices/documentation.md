# Best Practices — Documentation

Every catalog and collection carries two documentation files: an
[`AGENTS.md`](../portolan/core.md#agentsmd) for agents and a
[`README.md`](../portolan/core.md#readmemd) for humans. Core requires both files
and sets a content minimum for the README. This page covers what to put in
them, drawn from the catalogs whose documentation agents use most successfully
today.

## Two files, two audiences

Write the README for a person deciding whether to trust and use the data. Write
the AGENTS.md for an agent that has already committed to using it and now needs
to get queries right on the first try. The files share a subject but not a job,
so resist copying one into the other. A README schema table orients a reader;
an AGENTS.md that names the join key saves an agent a failed query.

## What belongs in AGENTS.md

The strongest agent guides published so far, such as the per-collection guides
in [Portolan NL](https://source.coop/cholmes/portolan-nl), share a recognizable
shape. In rough priority order:

- **What the data is, and how it connects.** Two or three sentences of context,
  then the identifiers that matter: which column is the stable key, and which
  codes join to other datasets. Portolan NL's administrative-areas guide points
  out that its CBS municipality codes are the join key used across all Dutch
  government data. That one sentence unlocks every cross-dataset query.

- **Runnable access patterns.** Show the exact DuckDB or GeoPandas invocation
  against the published URL, not a placeholder. For partitioned collections,
  include the glob pattern that reads every partition in one query. Note when
  remote reads stream over HTTP range requests, so agents query in place
  instead of downloading.

- **Quirks and caveats.** The highest-value section, because it holds what no
  schema can express. Real examples from Portolan NL: parcel ids are re-issued
  each year, so cross-year identity needs a spatial join; the RGB and infrared
  bands were flown in different seasons; black tile edges are unmasked nodata;
  one category exists in the data only from 2023 onward. Each sentence of this
  kind prevents a silently wrong answer.

- **The coordinate system, with consequences.** Name the CRS and say what
  follows from it. "EPSG:28992 is in metres, so `ST_Area` returns square
  metres. Divide by 10,000 for hectares" teaches more than the code alone.

- **Schema semantics.** Types and names live in `table:columns`; meaning lives
  here. Decode cryptic column names and code systems, state units, and when a
  collection ships several data files, document the schema of each file
  separately.

- **Query recipes worth stealing.** A handful of queries an analyst would run:
  an aggregation, a point-in-polygon lookup, a join into a related collection.
  Write recipes by running them, so they double as tests of the documentation.

- **Related collections and provenance.** Point at sibling collections that
  join well. Record how the data was produced, ideally as the exact command.
  Portolan NL's crop-parcels guide includes the full `ogr2ogr` invocation,
  flags and all, plus the geometry fix it needed.

Leave out what the machine metadata already says. Restating extents, licenses,
and row counts from `collection.json` pads the file without helping. Agents
read the JSON too, and duplicated facts drift.

## What makes a good README.md

Core requires a title, description, license, and provenance. Treat that as a
floor.

- **Numbers build trust.** State feature counts, coverage, and the vintage of
  the data in the opening paragraph. "All 63,073 nationally listed monuments"
  tells a reader more than "monument locations".

- **A schema table with described columns.** A column table with a description
  per field is the single most useful section for a human evaluating fit.
  Those descriptions belong in `table:columns` as well. Write them once in a
  manifest and generate both.

- **One runnable Quick Start.** A few lines of GeoPandas or DuckDB against the
  published URL. One tested snippet beats four aspirational ones.

- **Catalog-level READMEs are tables of contents.** At the root and at each
  sub-catalog, a collections table (title, feature count, geometry, one-line
  description) plus a short section on where the data comes from gives a
  reader the whole shape of the catalog in one screen.

- **Cross-reference the agent guide.** A one-line callout near the top,
  pointing agents at the AGENTS.md, routes each audience to its file.

## Keep the documentation honest

Drift between prose and metadata is the most common defect in otherwise strong
catalogs: a README that lists a collection the catalog no longer contains,
feature counts that disagree between pages, a Quick Start URL that returns 404
after a layout change, a guide claiming public domain while the metadata says
otherwise. Three habits prevent it:

- Generate documentation from the STAC metadata on every publish, so tables
  and counts cannot diverge from the catalog they describe.
- Run every example before publishing. A broken Quick Start costs more trust
  than no Quick Start.
- When a description exists only in prose, propagate it into the metadata.
  Hand-written schema tables that never reach `table:columns` help humans and
  strand agents.
