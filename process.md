# Specification Development Process

## Decision-Making

Portolan specification decisions are made collaboratively by the core team:

- Chris Holmes (@cholmes)
- Nissim Lebovits (@nlebovits)
- Maxym Malynowsky

## Open Questions

Open questions and unresolved design issues are tracked in [QUESTIONS.md](QUESTIONS.md).

## Architectural Decisions

Key architectural decisions and their rationale are documented in [DECISIONS.md](DECISIONS.md).

## Changes and Contributions

The specification follows a **CLI-first workflow**: the spec documents what the [portolan-cli](https://github.com/portolan-sdi/portolan-cli) does, not what it might do someday. This prevents drift between prose and implementation.

### Documenting Existing Features

- Changes to document existing CLI behavior are proposed via pull request
- PRs are discussed before merging
- Consensus among core team members is required for changes to core requirements

### Proposing New Features

- New feature ideas are tracked in [PROPOSALS.md](PROPOSALS.md)
- Once accepted, the CLI implements the feature first
- The spec is updated after CLI implementation ships

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Versioning

TBD: Semantic versioning strategy for the specification itself
