# Specification site

Build from the repository root with Python 3.12 or later and uv:

```sh
site/install-toolchain.sh site/.toolchain
export PATH="$PWD/site/.toolchain/bin:$PATH"
site_output=$(mktemp -d)
uv run --locked --script site/build.py --all --out "$site_output"
uv run --locked --script site/tests/check_site.py "$site_output"
uv run --locked --script site/tests/check_transforms.py
```

For one version:

```sh
uv run --locked --script site/build.py --ref HEAD --label next --out "$site_output"
```

Each version goes to `<out>/<label>/`, with
`downloads/portolan-spec-<label>.pdf` and `.epub`.
`--all` builds stable `vX.Y.Z` tags from `v0.2.0`, in version order.
Other `v*` tags produce a skip notice. Prereleases never become `latest`.
The build selects the descendant of `main` and `origin/main` for `next`.
It uses the available ref when only one exists and fails when they diverge.

The root redirect points to the newest release. `versions.json` follows
[mike 2.2.0](https://github.com/jimporter/mike/tree/v2.2.0), with `next` first
and releases in descending order. The newest release has the `latest` alias.
Each HTML page has a matching alias redirect that preserves its path, query,
and fragment. The root 404 page links to the newest release and `next`.
Published page links use directory URLs. The validator resolves them to
`index.html` on disk. For the org offline checker, use:

```sh
LYCHEE_ROOT_DIR="$site_output" ../portolan-ops/scripts/lychee.sh \
  --offline --index-files index.html "$site_output"
```

Each build exports its ref with `git archive` and changes temporary copies.
Links outside the document set point to that ref on GitHub. Images use raw
URLs. Released schema links retain their explicit version. Requirements show
severity, enforcement, and their source section on one metadata line.
The books contain core, formats, requirements, and best practices.
Incubating pages remain on the website.

A package version above the newest release produces `Draft of vX.Y.Z`.
Otherwise, `next` shows `Unreleased changes after vX.Y.Z` with the newest tag.
With no supported release tags, the draft notice omits the release link.

The output root must stay outside the checkout. The workflow's top-level
`_site` artifact directory is the only exception. The build refuses to replace
an existing version or alias directory without its `build-info.json` marker.
An output root must be empty or carry this script's `site-build.json` marker.
Unmarked directories remain untouched, including existing root pages and version lists.

`install-toolchain.sh` installs checksum-pinned Linux x86_64 binaries from the
[Pandoc release](https://github.com/jgm/pandoc/releases/tag/3.14) and
[Typst release](https://github.com/typst/typst/releases/tag/v0.15.1).
`build.py` checks both versions. It downloads checksum-pinned brand fonts from
the ops commit in `FONTS_SHA`, or reads them from `PORTOLAN_FONTS_DIR`.
The pinned brand kit has JetBrains Mono 400 and 600, with no 700 TTF.
The build adds Hanken Grotesk italics from the Google Fonts commit in
`GOOGLE_FONTS_SHA`. It verifies the font and its OFL license.
Only these pinned faces enter the PDF font directory. Typst ignores system
fonts and retains its embedded fallback faces.

- `build.py` uses CommonMark block tokens to preserve code while it rewrites
  links in list continuations. It stages documents and builds HTML, PDF, and EPUB.
- `mkdocs.yml` defines Zensical's theme and Markdown extensions, with its native
  mike version picker.
- `assets/` holds logos and styles. Load `_brand-vars.css` before `extra.css`.
- `overrides/` adds the draft notice to the theme's 404 page, and a kicker
  with the nav group name above each page title.
- `pandoc/` defines book typography, EPUB styles, and the template license.
- `tests/check_site.py` checks versions, aliases, requirement anchors, Git
  targets, images, PDF content, EPUB links, draft notices, and brand styles.
- `tests/check_transforms.py` covers transforms, guards, branch selection,
  and validator failures. It uses `HEAD`, or the ref from its `--ref` option.

Each Python entry point has a lockfile. After a dependency pin changes, run
`uv lock --script <script-path>` for that script. Run each script with `--locked`.

Output metadata identifies each archived source and its requirement sections.
The validator needs the source Git history but no network access.
