# Best Practices — Git-Backed Catalogs

## Why use git for catalog management?

Git gives publishers a controlled way to manage catalog metadata before and after publication. It provides change history, review, validation, and rollback without making git part of the published catalog itself.

A catalog may already be public when someone discovers an error. With a git-backed workflow, the publisher can correct the metadata in a pull request, validate the change, and publish the new version. If a published change causes a problem, git also provides the previous version and the changes that led to it.

This workflow is useful when several people or agents maintain a catalog, when contributors need to propose corrections, or when the catalog contains generated metadata. It also makes catalog maintenance more like software maintenance: changes are reviewed, checked, and recorded.

Nothing on this page is a requirement. Core defines what a catalog contains and how it declares conformance, but it does not define how publishers manage or publish catalogs. A catalog built and maintained by another method can conform just as well.

## Keep metadata in git, not data

The repository should contain the metadata needed to build and publish the catalog. Large data files should remain outside git and be referenced by URL, because git keeps old versions of committed files in its history.

[Fields of the World](https://github.com/fieldsoftheworld/ftw-data-catalog) separates repository files into three groups:

1. **Tracked and published:** STAC JSON, `README.md`, `AGENTS.md`, `llms.txt`, thumbnails, and logos.
2. **Tracked but not published:** build scripts, tests, publish configuration, and the repository's own README.
3. **Not tracked:** data files, credentials, and caches.

Committing large data files makes the repository expensive to clone and maintain. Git retains old binary versions even after files are deleted. The [St. Louis catalog](https://github.com/cholmes/portolan-catalog-stlouis) therefore ignores `catalog/**/*.parquet` and `catalog/**/*.pmtiles`.

A fresh clone may not contain the data needed by some checks. St. Louis uses `CI_LIGHT=1` in continuous integration to skip file-backed checks while keeping them available locally.

## Separate published metadata from repository files

The repository should have a clear directory containing the files that it publishes. The three catalogs studied here use a directory such as `catalog/`, while build scripts, tests, and source material remain elsewhere in the repository.

This makes the publication boundary easy to inspect. The publish tool can sync that directory without maintaining a separate list of files that it is allowed to publish.

A typical repository can use `catalog/` for published metadata, `staging/` or `sources/` for source material, `tools/` or `scripts/` for build code, and `tests/` for tests. A root `catalog.publish.yaml` can define the object-storage target and public base URL, keeping publication settings in one place.

The publication directory does not need to contain the data assets referenced by the catalog. For example, a generated STAC-GeoParquet item index can live directly in object storage and be referenced by a collection.

## Generate large catalogs

Small catalogs can be edited by hand. Large item collections should be generated instead of maintained as thousands of individual files, because generated files make reviews, diffs, and clones unnecessarily expensive.

Fields of the World shows this distinction within one catalog. It commits its prediction collections but not its Sentinel-2 feature items, which contain about 22,700 tiles per year across two years, or about 45,000 item files. Its `scripts/features/README.md` explains why committing them is impractical, and `.gitignore` enforces the policy with `catalog/features/*/items/`.

The generated items are replaced by a STAC-GeoParquet item index in object storage. The committed `collection.json` points to `items.parquet`, allowing clients to read one index instead of thousands of individual item files.

The repository should contain the generator and its inputs. [TriMet](https://github.com/cholmes/portolan-catalog-trimet) commits a `tools/` pipeline and its source listings while ignoring source Shapefiles that can be fetched again.

Generated output should be deterministic. TriMet's `tests/test_regen.py` rebuilds the catalog and compares it with the committed version, which lets the repository enforce the rule that contributors edit the generator rather than generated output.

## Validate changes with continuous integration

Use [rashid](https://github.com/portolan-sdi/rashid) for Portolan conformance and [stac-check](https://github.com/stac-utils/stac-check) for STAC validity and best practices. Both install from PyPI and run offline.

A minimal workflow is:

```yaml
- run: python -m pip install stac-check rashid
- run: rashid check catalog/
```

Run these checks on pull requests and before publication. This catches errors before a change reaches the published catalog and gives agents a clear feedback loop when they edit metadata.

A root catalog with no collections can pass validation, which allows a repository to remain valid from its first commit:

```console
$ rashid check catalog/ --schema
OK: 1 files checked, no findings.
```

### Handle validator differences

`stac-check` recommends a `self` link, but Portolan forbids it because a static catalog should not hardcode its own location when it may be mirrored or moved. Treat `stac-check` best-practice recommendations as advisory and use rashid as the Portolan conformance gate, as Fields of the World does in `tests/test_stac_valid.py`.

### Record accepted deviations

A catalog may have a reason to accept a validator finding temporarily, for example when it targets a spec change that has not shipped. TriMet records accepted deviations in [`docs/conformance.md`](https://github.com/cholmes/portolan-catalog-trimet/blob/main/docs/conformance.md), and its test fails when a finding is not listed there.

## Link a catalog to its repository

If a catalog is maintained in Git, publish two links on the root catalog:

* `vcs` points to the repository.
* `issues` points to its issue tracker.

Use absolute URLs because the repository is outside the published catalog.

```json
{ "rel": "vcs",    "href": "https://github.com/example/catalog", "title": "Source repository" },
{ "rel": "issues", "href": "https://github.com/example/catalog/issues", "title": "Issue tracker" }
```

This is a best practice, not a Core requirement. Not every catalog is maintained in Git, and a catalog does not say whether it is. A validator therefore cannot require these links.

Fields of the World already uses both links. The reasons for this convention are below.

### Why use links

Fields of the World also publishes `git:repository`, `git:ref`, and `git:provider` fields from an extension proposal that has not shipped. Portolan does not define these fields, and rashid does not interpret them.

The links provide what a consumer needs without adding new fields:

* The repository URL identifies the repository and its Git provider.
* The default branch needs no separate field.
* A repository path is only needed when the catalog lives inside a monorepo.
* A repository and its issue tracker are related resources, so link relations are a natural way to reference them.

`vcs` and `issues` are not IANA-registered relations, but clients that do not recognize them can ignore them.

### Why not `providers[host].url`

TriMet and St. Louis put their GitHub repository in the `url` of the `host` provider, both on the root catalog and on collections.

This is ambiguous because `host` identifies where the catalog's data is hosted, not where its metadata is maintained. FTW demonstrates the problem: its data is hosted by Source Cooperative, so its `host` provider correctly points to Source Cooperative rather than its Git repository.

It also provides no separate link to the issue tracker.

### Why the root catalog only

The repository maintains the catalog as a whole, so repeating the repository links on every collection adds duplication.

The root catalog is always reachable through the `root` link. A client that starts at a collection can therefore follow that link to find the repository.

### Include the links in prose too

The machine-readable links are the reliable way for software to find the repository and issue tracker. A README or catalog description can also tell people where to contribute.

TriMet's README and the Fields of the World description both do this. This is useful for human contributors but does not replace the links.

## Catalogs worth studying

* [ftw-data-catalog](https://github.com/fieldsoftheworld/ftw-data-catalog) — Metadata for a global machine-learning dataset with hundreds of gigabytes of data on Source Cooperative. Its `CLAUDE.md` documents the publication model and explains why a full recursive bucket listing was too slow.
* [portolan-catalog-stlouis](https://github.com/cholmes/portolan-catalog-stlouis) — Twenty collections mirrored from a city open-data portal, with the fetch, conversion, assembly, and validation workflow in the repository.
* [portolan-catalog-trimet](https://github.com/cholmes/portolan-catalog-trimet) — Eight transit datasets, with deterministic regeneration tests and a documented conformance-waiver process.

## Status

This page documents practices used by three publishers as of August 2026. The `vcs` and `issues` convention is already used by Fields of the World; the other practices are drawn from all three catalogs.

This is a best practice rather than a normative requirement. We can revisit it if more Git-backed catalogs reveal a better pattern.
