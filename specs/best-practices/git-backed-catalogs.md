# Best Practices — Git-Backed Catalogs

Core defines what a catalog contains and
[how it declares conformance](../portolan/core.md#conformance-and-versioning).
It says nothing about how you get there. This page covers one way of working
that several publishers arrived at independently: keep the catalog metadata in
a git repository, keep the data out of it, and let continuous integration
validate every change before it publishes.

Nothing here is a requirement. A catalog assembled by hand and uploaded once
conforms exactly as well as one built this way.

## Version control is what makes a catalog safe to edit

A published catalog is a single mutable tree in a bucket. Overwrite
`collection.json` with a broken one and the previous version is gone. There is
no undo, and the damage is live the moment the upload finishes.

Git supplies the undo. It also supplies three things that matter more as a
catalog grows:

- **A gate.** Continuous integration runs the validator on every pull request,
  so a change proves itself before it reaches the bucket. This matters most
  when an agent is doing the editing. An agent that can run the check and read
  the findings converges on a conforming catalog. An agent editing straight
  into a bucket is guessing.
- **A contribution path.** Someone who spots a wrong license or a stale
  description can open a pull request. Without a repository the best they can
  do is find an email address.
- **An explanation.** `git log` on a collection says why a description changed
  and who changed it. A published catalog carries an `updated` timestamp and
  nothing else.

## Metadata goes in git, data does not

The repository holds the STAC JSON, the READMEs, the agent guides, the styles,
and the logo. It does not hold the GeoParquet, the COGs, the PMTiles, or the
Zarr stores. Those live in object storage next to the published metadata, and
the repository references them by URL.

[Fields of the World](https://github.com/fieldsoftheworld/ftw-data-catalog)
states the split as three categories of file, which is the clearest framing of
it:

1. Tracked in git and published: the STAC JSON, `README.md`, `AGENTS.md`,
   `llms.txt`, thumbnails, logos.
2. Tracked in git and never published: the build scripts, the tests, the
   publish configuration, the repository's own README.
3. Neither: the data files, credentials, and caches. These are gitignored.

The failure mode of committing data is not subtle. Git stores every version of
every binary forever, so a 200 MB Parquet file regenerated weekly becomes tens
of gigabytes that every clone pays for, and no amount of later deletion
recovers it. The
[St. Louis mirror](https://github.com/cholmes/portolan-catalog-stlouis)
gitignores `catalog/**/*.parquet` and `catalog/**/*.pmtiles` by pattern, which
keeps the rule from depending on anyone remembering it.

One consequence is worth planning for. Because the data is absent from a fresh
clone, any check that reads bytes has nothing to read. St. Louis handles this
with a `CI_LIGHT=1` environment variable that skips the file-backed gates in
continuous integration while keeping them available locally, where the data
exists.

## The published directory is the whole contract

All three catalogs studied here use the same arrangement: one directory,
usually `catalog/`, that is synced to object storage exactly as it appears in
the repository. Everything inside it publishes. Nothing outside it can.

This is worth more than a convention about tidiness. It makes "what is live"
answerable by looking, and it makes publishing a credential or a build script
structurally impossible rather than merely unlikely. The publish tool needs no
allowlist because the directory boundary is the allowlist.

The rest of the repository then sorts itself out. Sources being prepared sit in
`staging/` or `sources/`. Build code sits in `tools/` or `scripts/`. Tests sit
in `tests/`. A `catalog.publish.yaml` at the root names the write target and
the public base URL, so the mapping between the two lives in one file rather
than being spread through the code.

## Generate the catalog once it outgrows hand-editing

A catalog of twenty collections can be edited by hand. An imagery catalog of
tens of thousands of items cannot, and committing them makes every clone and
every diff expensive for no gain.

Fields of the World draws this line inside a single catalog, which is the
clearest illustration of where it falls. Its prediction collections are
committed. Its Sentinel-2 feature collections are not: roughly 22,700 tiles per
year across two years is about 45,000 item files, and its
`scripts/features/README.md` says committing them is impractical. The
`.gitignore` enforces it with `catalog/features/*/items/`.

What replaces the items is not nothing. The committed `collection.json` points
at a STAC-GeoParquet `items.parquet` on object storage as the item index, so a
client reads one file instead of tens of thousands of links. The generator
writes the items and the index straight to the bucket, and the publish script
never sees them because they are outside the published directory.

What you commit instead is the generator and its inputs.
[TriMet](https://github.com/cholmes/portolan-catalog-trimet) commits a `tools/`
pipeline and the source listings it reads, with the Shapefiles gitignored and
re-fetchable. A reviewer reads a diff to `make_styles.py`. Nobody reads a diff
across sixty-three generated style files.

Generating the tree turns hand-editing into a bug, so it needs a check rather
than a request. TriMet's `tests/test_regen.py` rebuilds and compares against
the committed catalog, which is what makes "edit the generator, not the output"
enforceable.

## Validate every change before it lands

The gate is [rashid](https://github.com/portolan-sdi/rashid) for Portolan
conformance and [stac-check](https://github.com/stac-utils/stac-check) for STAC
validity and best practices. Both install from PyPI and run offline, so a
workflow is short:

```yaml
- run: python -m pip install stac-check rashid
- run: rashid check catalog/
```

A root catalog with no collections yet passes cleanly, so a repository is green
from its first commit:

```console
$ rashid check catalog/ --schema
OK: 1 files checked, no findings.
```

Two things surprise people wiring this up for the first time.

**stac-check will recommend a `self` link.** Portolan forbids one, because a
static catalog that hardcodes its own location cannot be mirrored or moved.
Treat stac-check's best-practice notes as advisory and let rashid be the gate,
which is what Fields of the World does in `tests/test_stac_valid.py`.

**Waivers need somewhere to live.** A catalog sometimes has a good reason to
carry a finding, such as targeting a spec change that has not shipped. TriMet
keeps a [`docs/conformance.md`](https://github.com/cholmes/portolan-catalog-trimet/blob/main/docs/conformance.md)
listing every accepted deviation with its reasoning, and its test fails on any
finding not on that list. The list cannot grow silently, which is the point.

## How a catalog points back at its repository is unsettled

Core's [`via`](../portolan/core.md#source-provenance) records where the data
came from. Nothing records where the catalog is maintained. A consumer holding
a published `catalog.json` has no dependable way to reach the repository that
produced it, which means no way to file the correction the README asked for.

As of August 2026 three encodings are in use, and every catalog studied here
uses at least two of them. No two use the same pair.

**Dedicated fields.** Fields of the World carries `git:repository`, `git:ref`,
and `git:provider`, plus `vcs` and `issues` link relations. This is the shape
of [an extension proposal](https://github.com/portolan-sdi/portolan-spec/issues/145)
that has not shipped, so nothing writes or reads the fields generically.
Portolan 0.1 defines no git extension and rashid ignores them, and the guard is
`tests/test_git_ext.py`, twenty lines of string equality against a literal URL.
The fields sit on the root catalog only, so a consumer who lands on a
`collection.json` sees nothing.

**The host provider's url.** TriMet and St. Louis both set the `url` of their
`host` provider to the GitHub repository, on the root and on every collection.
This adds no vocabulary, satisfies core's
[provider requirements](../portolan/core.md#providers) at the same time, and
reaches every level of the tree. The cost is ambiguity. A provider `url` means
"where this organization can be reached", so a repository there is
indistinguishable from a homepage, and there is nowhere to put the issue
tracker separately.

That encoding is also unavailable to some catalogs. Fields of the World hosts
its data on Source Cooperative, so its `host` provider is Source Cooperative,
which is the right answer to a different question.

**Prose.** TriMet's published README carries a table naming the catalog
repository and the browser repository, then asks directly for issues and pull
requests. The Fields of the World root description says the metadata is managed
in its repository and that pull requests are welcome. A person finds this. No
tool can act on it.

Nothing is recommended here. That every catalog reaches for two encodings is
the signal that none of them is sufficient alone, and the resolution belongs in
the spec rather than in three independent conventions. Weigh in on
[issue #145](https://github.com/portolan-sdi/portolan-spec/issues/145) if you
publish a catalog this affects.

## Catalogs worth studying

Three git-backed catalogs, readable end to end:

- [ftw-data-catalog](https://github.com/fieldsoftheworld/ftw-data-catalog) —
  metadata for a global machine-learning dataset whose data runs to hundreds
  of gigabytes on Source Cooperative. Its `CLAUDE.md` documents the publish
  model, including why a full recursive bucket listing was too slow and what
  replaced it.
- [portolan-catalog-stlouis](https://github.com/cholmes/portolan-catalog-stlouis)
  — twenty collections mirrored from a city open-data portal, with the
  fetch-convert-assemble pipeline and its gates in the repository.
- [portolan-catalog-trimet](https://github.com/cholmes/portolan-catalog-trimet)
  — eight transit datasets, notable for regeneration determinism tests and a
  written conformance-waiver policy.

## This is a discussion

This page describes what three publishers converged on by August 2026, which
is a small sample. The layout is consistent enough to write down. The
discovery question is not settled at all, and parts of this may look wrong
once more catalogs exist. If you maintain a git-backed catalog that solved
something differently, open an issue or a pull request on the
[spec repository](https://github.com/portolan-sdi/portolan-spec).
