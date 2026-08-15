<!-- ops-sync:begin — synced from portolan-sdi/portolan-ops. Edit there, not here. -->
# Portolan Agent Norms

These rules apply to AI agents working in any portolan-sdi repo. Every downstream repo carries this text verbatim as a synced block at the top of its own `AGENTS.md`. Repo-specific instructions live below the block and override the canonical rules in that repo only.

Claude Code does not read `AGENTS.md`. Each repo carries a one-line `CLAUDE.md` that imports it instead. Put repo-specific instructions in `AGENTS.md`, never in `CLAUDE.md`, which the sync overwrites.

## Ground Rules

The [portolan-spec](https://github.com/portolan-sdi/portolan-spec) repo is ground truth for the Portolan standard. The CLI, validator, registry, and every other tool implement the spec. They are downstream of it. Never describe the CLI as the source of truth. Propose spec changes in portolan-spec.

Before documenting any command, flag, or API, verify it exists in the shipped tool. A fabricated example persists beyond the session that wrote it.

Every repo uses Apache-2.0 except portolan-browser and portolan-nl-demo, which are ISC forks. See [norms/repos.md](https://github.com/portolan-sdi/portolan-ops/blob/main/norms/repos.md) for the record. Never introduce code under another license without a human decision recorded there.

Never bypass pre-commit hooks or CI gates. Green means green.

Write commits in conventional form. Squash-merge makes the pull request title become the commit message.

## Pull Requests and Issues

Write every issue and pull request in two layers. The human layer comes first: what is wrong or missing, why it matters, and what should happen instead. Someone who did not follow your investigation should understand it in about a minute. The agent layer comes after: evidence, implementation detail, constraints, edge cases, and verification.

There is no word limit. A 700-word issue is good when its first 150 words make the outcome obvious. A 150-word issue is bad when it compresses the meaning into prose the reader has to unpack. Optimize for fast comprehension, not for short tickets.

Write them in Simplified Technical English (ASD-STE100). The rules are an output style, `.claude/output-styles/simplified-technical-english.md`, which every repo carries. A hook prints it at session start. Sentences stay under 20 words and hold one idea. Use the active voice and simple verb forms only, so no gerund, no present participle, and no perfect tense. Use a verb rather than a noun made from a verb. Keep the technical content exactly as precise as it was, and simplify only the language around it. Describe the design as it stands now rather than the approaches you discarded.

The structural contract CI enforces on a pull request:

- The sections `## What changed`, `## Why`, and `## Verification` exist and are not empty.
- The prose references the issue the change resolves, as `#N` or its URL.
- Verification pastes the command you ran and its output in a fenced block under `## Verification`. It names the data it read, as a URL or catalog path.
- A change that alters no behavior ticks the waiver checkbox instead. Keep its wording intact because the check matches the phrase "does not alter behavior".

Good evidence shows the fix works against real data. Proving a command exits zero is not enough. Take the failing command from the issue, run it against the same catalog, and show it now succeeds. A wall of pytest output does not count.

Issues follow the same shape. A bug report shows the failure and names the data. A feature request shows where the current tool falls short, or what the workaround costs. A task states the outcome and the command that proves it is done.

Every repo uses the org issue template. The language itself is checked before a body is ever filed: `.claude/hooks/writing_check.py` runs on `gh issue create` and `gh pr create`, and reports the specific problems it found. Run `writing_check.py --print-rules` to read the rules. When it is wrong about a line, say so in the body with `<!-- ste-ok: RULE_ID why this is correct -->`. Dependabot is exempt from the CI check.

That check matches words and punctuation. It cannot see tone, padding, or prose that spends its length arguing for the work it describes, so passing it proves nothing about how the body reads. Read what you wrote before you file it, and cut the sentences that exist to make the change sound good.

## Documentation

Agents writing or restructuring documentation follow two exemplars named in [norms/docs.md](https://github.com/portolan-sdi/portolan-ops/blob/main/norms/docs.md). [obstore](https://github.com/developmentseed/obstore) demonstrates a concise, human-readable README that delegates to good docs elsewhere. [scaffold-docs-skill](https://github.com/dbreunig/scaffold-docs-skill) shows how to build docs that have a clear human-facing surface, maintain examples via tests so they never drift, and auto-generate API docs instead of duplicating them. Both keep documentation maintainable and robust. Draft top-down with human review between layers. Do not draft a README from a generic template or from memory.

Three rules apply to every docs change. Use title-case headings without emoji. Use absolute dates like "in July 2026", never "recently". Command examples must have been actually run against the shipped tool.

## Voice and Messaging

Every written artifact follows [VOICE.md](https://github.com/portolan-sdi/portolan-ops/blob/main/VOICE.md). This includes READMEs, PR and issue bodies, commit message bodies, docs, and lasting code comments. Apply it while drafting, not as cleanup.

Before drafting substantial public copy like a README, a docs page, or an announcement, fetch and read [VOICE.md](https://github.com/portolan-sdi/portolan-ops/blob/main/VOICE.md) and [copy/messaging.md](https://github.com/portolan-sdi/portolan-ops/blob/main/copy/messaging.md) in full. If you cannot fetch them, say so and stop. Write from the actual files, not from memory.

How Portolan is described comes from [copy/messaging.md](https://github.com/portolan-sdi/portolan-ops/blob/main/copy/messaging.md) alone.

## Org-Wide Facts

The canonical homepage is https://www.portolan-sdi.org/. Canonical URLs live in [copy/urls.md](https://github.com/portolan-sdi/portolan-ops/blob/main/copy/urls.md). Do not hardcode variants.

Community discussion happens in the [Portolan Google Group](https://groups.google.com/g/portolan) and the [Portolan channel](https://cloudnativegeo.slack.com/archives/C0A1JBH9529) in Cloud-Native Geo Slack. Planning lives in [org-level GitHub projects](https://github.com/orgs/portolan-sdi/projects/1).

## Contribution Rules

The [AI policy](https://github.com/portolan-sdi/portolan-ops/blob/main/policies/AI_POLICY.md) applies to every contribution. An agent may draft the diff and the pull request body. A human must read, understand, and approve both before review is requested. Agents never open PRs, post comments, or take action in shared spaces without human approval.

Follow the [contributing guide](https://github.com/portolan-sdi/portolan-ops/blob/main/policies/CONTRIBUTING.md) and the [code of conduct](https://github.com/portolan-sdi/portolan-ops/blob/main/policies/CODE_OF_CONDUCT.md).

## Sync Discipline

Files between `ops-sync` markers are synced from [portolan-ops](https://github.com/portolan-sdi/portolan-ops). They are overwritten on every sync run. To change one, edit it in portolan-ops, never in place.

One canonical home per fact. If a value like a color, URL, or policy line exists in portolan-ops, link to it rather than copying it.
<!-- ops-sync:end -->
