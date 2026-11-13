# Specification site

Build from the repository root with Python 3.12 or later and uv:

```sh
site/install-toolchain.sh site/.toolchain
export PATH="$PWD/site/.toolchain/bin:$PATH"
uv run --locked --script site/build.py --all --out site/out
uv run --script site/tests/check_site.py site/out
uv run --script site/tests/check_transforms.py
```

For one version:

```sh
uv run --locked --script site/build.py --ref v0.2.0 --label v0.2.0 --out site/out
```

The output goes to `<out>/<label>/`. Each version includes
`downloads/portolan-spec-<label>.pdf` and `downloads/portolan-spec-<label>.epub`.
`--all` builds SemVer tags from `v0.2.0` and a `next` draft from `origin/main`,
or `main` if no remote ref exists. It adds a root redirect to the newest
release and `versions.json` in mike format. Only the newest release has the
`latest` alias. The draft title is `next (draft)`.

Each build exports its ref with `git archive`. It changes only temporary
copies. Repository links outside the document set point to that ref on GitHub.
Released schema links point to the schema service. Requirements link to their
source sections. The books contain core, formats, requirements, and best
practices. Incubating pages remain on the website.

`install-toolchain.sh` installs checksum-pinned Linux x86_64 binaries from the
[Pandoc release](https://github.com/jgm/pandoc/releases/tag/3.14) and
[Typst release](https://github.com/typst/typst/releases/tag/v0.15.1).
`build.py` checks both versions. It downloads checksum-pinned brand fonts from
the ops commit in `FONTS_SHA`, or reads them from `PORTOLAN_FONTS_DIR`.
The pinned brand kit has JetBrains Mono 400 and 600, with no 700 TTF.

- `build.py` stages documents, rewrites links, and builds HTML, PDF, and EPUB.
- `build.py.lock` fixes the Python dependency set. Refresh it with
  `uv lock --script site/build.py` after a pin change.
- `mkdocs.yml` defines the Zensical theme and Markdown extensions.
  Zensical 0.1.1 supports the mike version provider in its config and templates.
- `assets/` holds the brand logos and styles. Load `_brand-vars.css` first.
- `overrides/` adds the draft notice to the theme’s 404 page.
- `pandoc/` defines the book typography and EPUB styles.
- `tests/check_site.py` checks a version directory or a complete output root.
  It compares requirements with the archived manifest and checks local links,
  EPUB links, draft notices, download formats, and brand styles.
- `tests/check_transforms.py` checks links, fences, draft notices, and requirement
  sections on local and remote main refs.

The output includes `build-info.json` and `requirements.json` so checks can
identify each archived source and its requirement sections. Validation needs
the source Git history but no network access.
