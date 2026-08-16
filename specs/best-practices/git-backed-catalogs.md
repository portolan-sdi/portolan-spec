# Best Practices — Git-Backed Catalogs

## Why use git for catalog management?

Git gives publishers a controlled way to manage catalog metadata before and after publication. It provides change history, review, validation, and rollback without making Git part of the published catalog itself.

A catalog may already be public when someone discovers an error. With a git-backed workflow, the publisher can correct the metadata in a pull request, validate the change, and publish the new version. If a published change causes a problem, Git also preserves the previous version and the changes that led to it.

This workflow is useful when several people or agents maintain a catalog, when contributors need to propose corrections, or when the catalog contains generated metadata. It makes catalog maintenance more like software maintenance: changes are reviewed, checked, and recorded.

Nothing on this page is a requirement. Core defines what a catalog contains and how it declares conformance, but it does not define how publishers manage or publish catalogs. A catalog maintained another way can conform just as well.

## Keep metadata in git, not data

The repository should contain the metadata needed to build and publish the catalog. Large data files should remain outside Git and be referenced by URL, because Git keeps old versions of committed files in its history.

Fields of the World separates repository files into three groups:

1. **Tracked and published:** STAC JSON, `README.md`, `AGENTS.md`, `llms.txt`, thumbnails, and logos.
2. **Tracked but not published:** build scripts, tests, publish configuration, and the repository's own README.
3. **Not tracked:** data files, credentials, and caches.

Committing large data files makes the repository expensive to clone and maintain. Git retains old binary versions even after files are deleted. The St. Louis catalog therefore ignores `catalog/**/*.parquet` and `catalog/**/*.pmtiles`.

A fresh clone may not contain the data needed by some checks. St. Louis uses `CI_LIGHT=1` in continuous integration to skip file-backed checks while keeping them available locally.

## Separate published metadata from repository files

The repository should have a clear directory containing the files that it publishes. The three catalogs studied here use a directory such as `catalog/`, while build scripts, tests, and source material remain elsewhere in the repository.

This makes the publication boundary easy to inspect. It also lets tools such as STAC Browser open `catalog/catalog.json` directly from the repository to preview and inspect the catalog.

The publication directory does not need to contain the data assets referenced by the catalog. For example, a generated STAC-GeoParquet item index can live directly in object storage and be referenced by a collection.

A typical repository can use `catalog/` for published metadata, `staging/` or `sources/` for source material, `tools/` or `scripts/` for build code, and `tests/` for tests. A root `catalog.publish.yaml` can define the object-storage target and public base URL, keeping publication settings in one place.

## Keep links relative

Core requires relative structural links and says nothing about `self` links. For a git-backed catalog the `self` link is worth leaving out of the tracked tree, and the reason is the workflow rather than the standard.

A git-backed catalog is authored in one place and served from another. The same JSON has to be valid in the repository, in whatever preview a pull request builds, and in production. Relative links give all three for free: one tree of bytes, checked by CI on a laptop or a runner, published unchanged. A `self` link names one of those locations, so the copy in git is either wrong for the other two or has to be rewritten on the way out.

That cost is small in absolute terms, since only the root catalog carries the link. It is annoying in a repository. A tracked file whose correct content depends on where it was deployed produces diff noise, and it conflicts on merge or rebase for reasons that have nothing to do with the change under review. It is also a file that a contributor can get wrong in a pull request without any local check catching it.

The pull is real in the other direction. A published catalog with no `self` link records nothing about where it lives. A reader holding a copy cannot tell where it came from, and a tool reading the metadata cannot turn a relative asset href into a URL without being handed a base separately. That is the case STAC's relative published catalog answers.

The two goals are compatible if the publish step owns the link. Keep the tracked tree free of `self` links, and let the tool that uploads add an absolute one to the root catalog, since it is the only thing that knows the destination. The publish configuration already holds that URL: a `catalog.publish.yaml` with a `public_base` key, as described above, has everything the step needs. The repository stays portable and the published catalog stays self-describing, which is the split a git-backed workflow wants.

Two practices reinforce the same point. Assets are addressed relative to the collection that declares them, which keeps a collection movable within the tree. Tools that generate documentation from the catalog, such as a README with a file table, need an absolute base to make those paths clickable; give them the publish configuration rather than absolute hrefs in the metadata.

## Keep the tools and inputs

The repository should contain the scripts, tools, and source inputs used to produce the catalog. This can be custom code or existing tools such as GDAL/OGR, `gpio`, or `portolan-cli`.

Sharing this pipeline makes the catalog easier to reproduce and maintain. It also gives other publishers concrete examples of different ways to build catalogs and gives tool maintainers real workflows to improve.

TriMet commits its `tools/` pipeline and source listings while ignoring source Shapefiles that can be fetched again.

Generated output should be deterministic. TriMet's `tests/test_regen.py` rebuilds the catalog and compares it with the committed version, which lets the repository enforce the rule that contributors edit the generator rather than generated output.

## Generate large catalogs

Small catalogs can be edited by hand. Large item collections should be generated instead of maintained as thousands of individual files, because generated files make reviews, diffs, and clones unnecessarily expensive.

Fields of the World shows this distinction within one catalog. It commits its prediction collections but not its Sentinel-2 feature items, which contain about 22,700 tiles per year across two years, or about 45,000 item files. Its `scripts/features/README.md` explains why committing them is impractical, and `.gitignore` enforces the policy with `catalog/features/*/items/`.

The generated items are replaced by a STAC-GeoParquet item index in object storage. The committed `collection.json` points to `items.parquet`, allowing clients to read one index instead of thousands of individual item files.

## Validate changes with continuous integration

Use rashid for Portolan conformance and stac-check for STAC validity and best practices. Both install from PyPI and run offline.

A minimal workflow is:

```yaml id="j49h8x"
- run: python -m pip install stac-check rashid
- run: rashid check catalog/
```

Run these checks on pull requests and before publication. This catches errors before a change reaches the published catalog and gives agents a clear feedback loop when they edit metadata.

A root catalog with no collections can pass validation, which allows a repository to remain valid from its first commit:

```console id="0v3l6e"
$ rashid check catalog/ --schema
OK: 1 files checked, no findings.
```

### Handle validator differences

`stac-check` recommends a `self` link, but Portolan forbids it because a static catalog should not hardcode its own location when it may be mirrored or moved. Treat `stac-check` best-practice recommendations as advisory and use rashid as the Portolan conformance gate, as Fields of the World does in `tests/test_stac_valid.py`.

### Record accepted deviations

A catalog may have a reason to accept a validator finding temporarily, for example when it targets a spec change that has not shipped. TriMet records accepted deviations in `docs/conformance.md`, and its test fails when a finding is not listed there.

## Link a catalog to its repository

If a catalog is maintained in Git, publish two links on the root catalog:

* `vcs` points to the repository.
* `issues` points to its issue tracker.

Use absolute URLs because the repository is outside the published catalog.

```json id="5cwv69"
{
  "rel": "vcs",
  "href": "https://github.com/example/catalog",
  "title": "Source repository"
},
{
  "rel": "issues",
  "href": "https://github.com/example/catalog/issues",
  "title": "Issue tracker"
}
```

Fields of the World already publishes both links.

The [STAC VCS Extension](https://github.com/stac-extensions/vcs) is also being developed to describe version-control information such as the VCS type, branch, commit, and tag. It is currently a proposal and is not part of Portolan. The extension can complement the repository link: `vcs` identifies the repository, while the extension can identify the particular version of the catalog that came from it.

The `issues` link serves a different purpose. It gives people and tools a direct place to report problems or propose corrections. STAC tooling could use this link to provide issue-reporting features directly from a catalog browser.

These links are a best practice, not a Core requirement. Not every catalog is maintained in Git, and a published catalog does not say whether a repository exists. A validator therefore cannot require them.

## Include contribution guidance

The repository should explain how contributors can propose changes and report problems. A root `README.md` can point people to the relevant tools, documentation, issues, and pull requests.

The machine-readable `vcs` and `issues` links make the repository and issue tracker discoverable to software. The README and catalog description can provide additional context for human contributors.

## Catalogs worth studying

* **ftw-data-catalog** — Metadata for a global machine-learning dataset with hundreds of gigabytes of data on Source Cooperative. Its `CLAUDE.md` documents the publication model and explains why a full recursive bucket listing was too slow.
* **portolan-catalog-stlouis** — Twenty collections mirrored from a city open-data portal, with the fetch, conversion, assembly, and validation workflow in the repository.
* **portolan-catalog-trimet** — Eight transit datasets, with deterministic regeneration tests and a documented conformance-waiver process.

## Status

This page documents early practices in August 2026. These practices may change as more git-backed catalogs are published.

The `vcs` and `issues` links are a recommended convention, not a Portolan requirement. A future spec change could add a `SHOULD` for catalogs maintained in Git; that can be evaluated separately as the STAC VCS Extension and related link relations mature.

If you maintain a git-backed catalog and use a different approach, open an issue or pull request on the Portolan spec repository.
