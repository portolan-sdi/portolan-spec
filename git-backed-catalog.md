# Git-Backed Catalog Extension (Proposal / RFC)

- **Title:** Git-Backed Catalog
- **Field prefix:** `git`
- **Scope:** Catalog, Collection
- **Maturity:** Proposal
- **Schema:** [`schemas/git/v1.0.0/schema.json`](schemas/git/v1.0.0/schema.json)

## Motivation

Portolan catalogs are increasingly authored and maintained as **git repositories** — the repo
*is* the catalog: STAC metadata + cloud-native data, edited via **pull requests**, validated in
**CI**, and published to object storage by an action. This is a natural fit for Portolan's
"static files, no servers" model and adds a real collaboration layer (contribution, review,
versioned history) for free.

The spec today cannot express this. [`rel: "via"`](core.md) records where the *data* came from;
it says nothing about where the **catalog itself** is maintained, how to contribute to it, how to
subscribe to changes, or whether its host is sovereign. This extension adds that — additively, so
a plain STAC client simply ignores it.

## Fields

On a **Catalog** or **Collection** (inherited from the root catalog unless overridden):

| Field | Type | Required | Description |
|---|---|---|---|
| `git:repository` | string (uri) | **yes** | URL of the source repository that is the catalog's source of truth. |
| `git:ref` | string | no | Branch or tag the published catalog is built from (default `main`). |
| `git:provider` | string | no | One of `github`, `gitlab`, `forgejo`, `gitea`, `other`. |
| `git:sovereign` | boolean | no | Whether the repository host is sovereign / self-hosted (e.g. an EU-hosted Forgejo = `true`; `github.com` = `false`). Lets consumers reason about jurisdiction. |
| `git:path` | string | no | Path within the repository, when one repo holds multiple catalogs (monorepo). |

On a **Collection** additionally:

| Field | Type | Required | Description |
|---|---|---|---|
| `git:edit_url` | string (uri) | no | Deep link to edit this collection's source (a "propose a change" link). |

## Link relations (recommended)

| `rel` | Target | `type` |
|---|---|---|
| `vcs` | the source repository (human-browsable) | `text/html` |
| `issues` | contribution / feedback channel (issues, discussions) | `text/html` |
| `monitor` | a change feed to subscribe to updates (e.g. an Atom commit feed, optionally path-scoped to one collection) | `application/atom+xml` |

These are **complementary to `rel: "via"`**: `via` records the original *data* source; this
extension records the *catalog's* source and how to participate in it.

## Example

```json
{
  "type": "Catalog",
  "stac_version": "1.0.0",
  "stac_extensions": [
    "https://portolan-sdi.github.io/git-backed-catalog/v1.0.0/schema.json"
  ],
  "id": "statistics-finland",
  "title": "Statistics Finland — Portolan catalog",
  "git:repository": "https://github.com/example/portolan-statfi-catalog",
  "git:ref": "main",
  "git:provider": "github",
  "git:sovereign": false,
  "links": [
    { "rel": "root", "href": "./catalog.json", "type": "application/json" },
    { "rel": "vcs", "href": "https://github.com/example/portolan-statfi-catalog", "type": "text/html", "title": "Source repository" },
    { "rel": "issues", "href": "https://github.com/example/portolan-statfi-catalog/issues", "type": "text/html", "title": "Report issues / request data" },
    { "rel": "monitor", "href": "https://github.com/example/portolan-statfi-catalog/commits/main.atom", "type": "application/atom+xml", "title": "Change feed" }
  ]
}
```

## Why it matters

A git-backed catalog turns "publishing open data" into "data as code": contributions arrive as
pull requests, a CI gate validates them before they can publish, history and provenance are free,
and consumers (including AI agents) can **discover how to contribute and how to subscribe** —
not just how to read. `git:sovereign` makes the hosting/jurisdiction question machine-readable,
which matters for sovereign-SDI use cases (the same catalog can move from a US host to a
self-hosted EU one with one field flip).

## Relation to other work

- **Complements `rel: "via"`** (data provenance) — distinct concern (catalog source vs data source).
- **Pairs with the STAC Iceberg extension** (table connectivity) and the STAC Table extension
  (schema) — orthogonal.
- Intended to underpin a Portolan **"GitOps" best-practice**: repo → CI validate → publish to
  object storage, with contribution, subscription and sovereignty all declared in the metadata.

## Open questions for the WG

1. Standalone extension repo (like `stac-iceberg-extension`) vs. a Portolan best-practice doc?
2. `git:sovereign` boolean vs. a richer `host`/`jurisdiction` object?
3. Should `monitor` be generalized (webhooks, RSS) beyond Atom?
