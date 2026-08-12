# Best Practices — Git-Backed Catalogs

Keep catalog metadata in git, keep data outside git, and validate every
change before publication. This gives publishers a safe, reviewable way to
maintain a catalog.

Core defines catalog content and
[conformance declarations](../portolan/core.md#conformance-and-versioning).
It does not define a publishing workflow. This page describes one approach
that several publishers adopted independently.

Nothing on this page is a requirement. A catalog built by hand and uploaded
once conforms just as well as a catalog maintained this way.

## Version Control Makes Catalogs Safer to Edit

A published catalog is one mutable tree in a bucket. If you overwrite
`collection.json` with a broken file, the earlier file is gone and the damage
is live as soon as the upload finishes.

Git provides an undo path. As a catalog grows, it also provides three useful
things:

- **A gate.** Continuous integration runs the validator on each pull request,
  so a change must prove itself before it reaches the bucket. This is most
  useful when an agent edits the catalog: an agent can run the check and read
  its findings, while an agent editing the bucket directly must guess.
- **A contribution path.** Someone who finds a wrong license or stale
  description can open a pull request. Without a repository, they can only
  try to find an email address.
- **An explanation.** `git log` shows why a collection description changed
  and who changed it. A published catalog has only an `updated` timestamp.

## Put Metadata in Git, Not Data

The repository contains STAC JSON, READMEs, agent guides, styles, and logos.
It does not contain GeoParquet, COGs, PMTiles, or Zarr stores. Those data files
live in object storage next to the published metadata, and the repository
references them by URL.

[Fields of the World](https://github.com/fieldsoftheworld/ftw-data-catalog)
uses three file groups:

1. Tracked in git and published: STAC JSON, `README.md`, `AGENTS.md`,
   `llms.txt`, thumbnails, and logos.
2. Tracked in git and not published: build scripts, tests, publish
   configuration, and the repository's own README.
3. Neither: data files, credentials, and caches. Git ignores these files.

Committing data fails in a predictable way. Git stores every binary version
forever, so a 200 MB Parquet file regenerated each week grows into tens of
gigabytes that every clone must download. Deleting it later does not recover
that space. The [St. Louis mirror](https://github.com/cholmes/portolan-catalog-stlouis)
ignores `catalog/**/*.parquet` and `catalog/**/*.pmtiles`, so the rule does not
depend on memory.

Plan for one consequence: a fresh clone has no data files, so checks that read
data have nothing to read. St. Louis uses `CI_LIGHT=1` in continuous
integration to skip file-backed gates there, while keeping those gates
available locally where the data exists.

## The Published Directory Is the Full Contract

All three catalogs studied here use one directory, usually `catalog/`, which
is synced to object storage exactly as it appears in the repository. Everything
inside it publishes, and nothing outside it can publish.

This is more than tidy organization. It makes it clear what is live and makes
publishing a credential or build script structurally impossible. The publish
tool needs no allowlist because the directory boundary is the allowlist.

The rest of the repository can then use clear locations. Prepared sources go
in `staging/` or `sources/`, build code in `tools/` or `scripts/`, and tests in
`tests/`. A root `catalog.publish.yaml` names the write target and public base
URL, keeping that mapping in one file rather than spreading it through code.

## Generate Catalogs That Are Too Large to Edit by Hand

You can edit a catalog with twenty collections by hand. You cannot reasonably
edit an imagery catalog with tens of thousands of items, and committing those
items makes clones and diffs expensive without benefit.

Fields of the World shows this boundary within one catalog. It commits its
prediction collections, but not its Sentinel-2 feature collections: about
22,700 tiles per year for two years create about 45,000 item files. Its
`scripts/features/README.md` says committing them is impractical, and
`.gitignore` enforces this with `catalog/features/*/items/`.

The replacement is not an empty catalog. The committed `collection.json`
points to an `items.parquet` STAC-GeoParquet item index in object storage, so a
client reads one file instead of many thousands of links. The generator writes
the items and index directly to the bucket; the publish script does not see
them because they are outside the published directory.

Commit the generator and its inputs instead. [TriMet](https://github.com/cholmes/portolan-catalog-trimet)
commits a `tools/` pipeline and the source listings it reads, while ignoring
Shapefiles that it can fetch again. A reviewer can read a change to
`make_styles.py`; they should not need to review sixty-three generated style
files.

Generated trees make manual edits a bug, so enforce the rule with a check.
TriMet's `tests/test_regen.py` rebuilds the catalog and compares it with the
committed version. That makes “edit the generator, not the output” enforceable.

## Validate Each Change Before It Lands

Use [rashid](https://github.com/portolan-sdi/rashid) to check Portolan
conformance and [stac-check](https://github.com/stac-utils/stac-check) to
check STAC validity and best practices. Both install from PyPI and run offline,
so the workflow is short:

```yaml
- run: python -m pip install stac-check rashid
- run: rashid check catalog/
```

A root catalog with no collections passes cleanly. This lets a repository stay
green from its first commit:

```console
$ rashid check catalog/ --schema
OK: 1 files checked, no findings.
```

Two details often surprise people setting this up.

**stac-check recommends a `self` link.** Portolan forbids it because a static
catalog that hardcodes its own location cannot be mirrored or moved. Treat
stac-check best-practice notes as advice and let rashid be the gate, as Fields
of the World does in `tests/test_stac_valid.py`.

**Waivers need a home.** A catalog can have a valid reason to keep a finding,
such as when it targets a spec change that is not yet available. TriMet keeps a
[`docs/conformance.md`](https://github.com/cholmes/portolan-catalog-trimet/blob/main/docs/conformance.md)
list of accepted deviations and their reasons. Its test fails on any finding
not on that list, so the list cannot grow silently.

## A Catalog's Link to Its Repository Is Not Settled

Core's [`via`](../portolan/core.md#source-provenance) records the data source.
It does not record where a catalog is maintained. A consumer with a published
`catalog.json` therefore has no dependable path to the repository that built
it, or to a place to report a correction.

As of August 2026, three encodings are in use. Every catalog studied here uses
at least two, and no two use the same pair.

**Dedicated fields.** Fields of the World uses `git:repository`, `git:ref`,
and `git:provider`, plus `vcs` and `issues` link relations. This follows the
shape of [an extension proposal](https://github.com/portolan-sdi/portolan-spec/issues/145)
that has not shipped, so tools do not read or write these fields in a general
way. Portolan 0.1 has no git extension and rashid ignores the fields. The guard
is `tests/test_git_ext.py`, which uses twenty lines of string equality against
a literal URL. The fields appear only on the root catalog, so a consumer who
opens a `collection.json` does not see them.

**The host provider's URL.** TriMet and St. Louis set the `url` of their `host`
provider to the GitHub repository, both on the root and on every collection.
This needs no new vocabulary, meets Core's
[provider requirements](../portolan/core.md#providers), and reaches every tree
level. It is ambiguous: a provider `url` means where an organization can be
reached, so a repository URL is not distinct from a homepage and has no place
for a separate issue tracker.

This approach also does not work for every catalog. Fields of the World hosts
its data on Source Cooperative, so Source Cooperative is its `host` provider.
That correctly answers a different question.

**Prose.** TriMet's published README names both the catalog repository and the
browser repository, then asks directly for issues and pull requests. The
Fields of the World root description says that its repository manages the
metadata and that pull requests are welcome. People can use this information;
tools cannot.

This page recommends none of these options. The fact that each catalog uses two
encodings shows that no one encoding is enough. The decision belongs in the
spec, not in three separate conventions. If you publish a catalog affected by
this, contribute to [issue #145](https://github.com/portolan-sdi/portolan-spec/issues/145).

## Catalogs Worth Studying

Three git-backed catalogs can be read end to end:

- [ftw-data-catalog](https://github.com/fieldsoftheworld/ftw-data-catalog) —
  metadata for a global machine-learning dataset with hundreds of gigabytes of
  data on Source Cooperative. Its `CLAUDE.md` explains the publish model,
  including why a full recursive bucket listing was too slow and what replaced
  it.
- [portolan-catalog-stlouis](https://github.com/cholmes/portolan-catalog-stlouis)
  — twenty collections mirrored from a city open-data portal, with its
  fetch-convert-assemble pipeline and gates in the repository.
- [portolan-catalog-trimet](https://github.com/cholmes/portolan-catalog-trimet)
  — eight transit datasets, with deterministic regeneration tests and a written
  conformance-waiver policy.

## This Is a Discussion

This page describes patterns that three publishers had reached by August 2026.
That is a small sample. The layout is consistent enough to document, but the
repository-discovery question is not settled, and more catalogs may show that
some parts are wrong.

If you maintain a git-backed catalog that uses a different solution, open an
issue or pull request on the
+[spec repository](https://github.com/portolan-sdi/portolan-spec).
