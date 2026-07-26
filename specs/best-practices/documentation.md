# Best Practices — Documentation

Every catalog and collection carries two documentation files: an
[`AGENTS.md`](../portolan/core.md#agentsmd) for agents and a
[`README.md`](../portolan/core.md#readmemd) for humans. Core requires both files
and sets a content minimum for the README. This page covers what to put in
them, drawn from the catalogs whose documentation agents use most successfully
today.

The goal of all of it, borrowed from the
[Candid Core Framework](https://lettersfromthreadedfoundry.substack.com/p/candid-core-framework)
(Trochim & Roy, 2025, [doi:10.5281/zenodo.15227664](https://doi.org/10.5281/zenodo.15227664)),
is to help users "swiftly, accurately, and confidently assess a dataset's
practical value". Discovery is the solved half of the problem: a well-formed
STAC catalog can be found and crawled. What documentation adds is
evaluability. In the framework's words, effective metadata must transparently
communicate "articulated data quality, explicitly acknowledged biases, candid
limitations, recommended use cases informed by real-world insights, and
collective community knowledge shared transparently."

## Two files, two audiences

Write the README for a person deciding whether to trust and use the data. Write
the AGENTS.md for an agent that has already committed to using it and now needs
to get queries right on the first try. The files share a subject but not a job,
so resist copying one into the other. A README schema table orients a reader;
an AGENTS.md that names the join key saves an agent a failed query.

The STAC `description` field is a third surface, and it overlaps the README by
design. They are two interfaces to the same facts: the description serves
browsers, search results, and item lists; the README serves a person who has
already clicked through. Duplication between them is fine. Drift is not, so
generate both from one source where you can, and when you hand-edit one,
update the other.

## Evaluate the data, not just describe it

A schema table and an extent tell a user what the data is. The documentation
that earns trust also tells them what it is *for*, and what it is not for.
Future versions of this guidance may make these required sections; today they
separate complete documentation from excellent documentation.

- **Suggested uses.** Name what the data has actually supported: the analysis
  in the source paper, the operational program it feeds, the question a known
  user answered with it. Attributed, real uses beat abstract claims of
  suitability. Keep them informative rather than restrictive; a list of
  proven uses invites reuse, a fence around "intended use" forecloses it.

- **Application limitations and inappropriate uses.** Say when *not* to use
  the data, in plain terms. The [FTW global
  catalog](https://source.coop/ftw/global-data) does this well: a field
  polygon "is a *remote-sensing field unit*, **not** a cadastral/legal parcel.
  This is not a land-tenure product." One sentence like that prevents a whole
  category of misuse that no accuracy figure would catch.

- **Accuracy and uncertainty, quantified.** Report the validation numbers,
  and where confidence varies, ship it as data: a per-record confidence
  column or an uncertainty layer, with the derivation and a recommended
  threshold documented. An honest 85% with a map of where it is weak serves
  users better than an unqualified 95%.

- **Known biases.** State where the data is weaker, by region, season, or
  class, and why. FTW again: the confidence layer "is conservative outside
  the training distribution (e.g. smallholder systems)", with the suggested
  mitigation alongside. Naming a bias is what lets a user work around it.

- **Definitions.** When the data asserts a category — forest, urban, field,
  building — state the threshold and cite the definition used. Published
  forest datasets disagree by millions of square kilometres on definitional
  grounds alone. The category boundary is metadata, not a footnote.

Put these caveats where they will be seen. A warning buried in prose is easily
missed once the data itself looks clean and continuous, so state limitations
in the README *and* carry what you can in structured metadata: confidence as a
column, quality masks as assets, definitions in column descriptions.

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
floor. The README is the landing page: for most users, human or agent, it is
the first and often only thing read before deciding to use the data or move
on. Write it as a narrative that carries a reader from "what is this" to
"how do I get it", not as a checklist of fields.

- **Numbers build trust.** State feature counts, coverage, and the vintage of
  the data in the opening paragraph. "All 63,073 nationally listed monuments"
  tells a reader more than "monument locations".

- **Links carry the context.** Link the paper that describes the methods, the
  agency page the data comes from, the program that funded collection, and
  the datasets it derives from, in flowing sentences where each source is
  introduced, not as a bare reference list at the bottom. The [Planet
  Venezuela earthquake
  catalog](https://source.coop/planet/venezuela-earthquake-2026-06-24) quotes
  its source program's own description and links every location name to the
  scenes it describes; a reader leaves its README knowing the event, the
  sensors, and the program, without having opened another tab first.

- **A schema table with described columns.** A column table with a description
  per field is the single most useful section for a human evaluating fit.
  Those descriptions belong in `table:columns` as well. Write them once in a
  manifest and generate both.

- **One runnable Quick Start.** The exact invocation that gets the data, near
  the top, against the published URL. One tested snippet that answers "this
  is how you get it" beats four aspirational ones.

- **Escalate to the interesting access pattern.** Past the Quick Start, skip
  the third and fourth basic query; show the pattern a reader would not have
  guessed. For a raster collection, that is treating the whole collection as
  one dataset: the Venezuela catalog turns its scene collection into a single
  xarray cube with `odc.stac.load`, and into one GDAL VRT from its
  STAC-GeoParquet index. For vectors, it is the glob query across every
  partition. One advanced, runnable pattern teaches what the catalog is
  capable of.

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
otherwise. An agent guide is especially prone to surviving a refactor intact,
still describing a structure the catalog no longer has, complete with example
queries that filter on values that can no longer match. Three habits prevent
it:

- Generate documentation from the STAC metadata on every publish, so tables
  and counts cannot diverge from the catalog they describe.
- Run every example before publishing. A broken Quick Start costs more trust
  than no Quick Start.
- When a description exists only in prose, propagate it into the metadata.
  Hand-written schema tables that never reach `table:columns` help humans and
  strand agents.
