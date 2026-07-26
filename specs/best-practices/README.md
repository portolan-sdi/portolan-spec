# Best Practices

This folder is **guidance, not conformance**. Nothing here is a MUST/SHOULD/MAY
requirement — those live in [`specs/portolan/`](../portolan/). These are discussion
pieces and recommendations on how to build good Portolan catalogs, aimed at both
the people who publish them and the agents that consume them.

Over time this is also where the **catalog grader** will live — the criteria behind
rating a catalog A+, B, C, and so on.

## Contents

- [`styling.md`](styling.md) — making visualization styles that are clear and
  distinctive across a catalog.
- [`conversion-defaults.md`](conversion-defaults.md) — the COG, partition, and
  thumbnail settings the Portolan CLI uses when converting source data.

## Planned

Stubs for guidance we intend to write (contributions welcome — open a PR):

- **What belongs in your `AGENTS.md`** — how to write the agent-facing guide that
  core requires, and what actually helps an agent use the data.
- **What makes a good `README.md`** — the human-facing counterpart.
- **Catalog philosophy** — how to think about scoping, organizing, and maintaining
  a Portolan catalog; pointers to exemplary catalogs.
- **The grader** — the rubric for rating catalog quality.
