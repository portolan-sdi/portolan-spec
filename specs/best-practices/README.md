# Best Practices

This folder is **guidance, not conformance**. Nothing here is a MUST/SHOULD/MAY
requirement — those live in [`specs/portolan/`](../portolan/). These are discussion
pieces and recommendations on how to build good Portolan catalogs, aimed at both
the people who publish them and the agents that consume them.

## Contents

- [`documentation.md`](documentation.md) — what belongs in your `AGENTS.md` and
  what makes a good `README.md`.
- [`philosophy.md`](philosophy.md) — how to think about scoping, organizing, and
  maintaining a Portolan catalog; pointers to exemplary catalogs.
- [`git-backed-catalogs.md`](git-backed-catalogs.md) — keeping catalog metadata
  in a repository, with the data outside it, and validating every change in CI.
- [`grader.md`](grader.md) — the rubric for rating catalog quality, A+ through F.
- [`styling.md`](styling.md) — making visualization styles that are clear and
  distinctive across a catalog.
- [`conversion-defaults.md`](conversion-defaults.md) — the COG, partition, and
  thumbnail settings the Portolan CLI uses when converting source data.
