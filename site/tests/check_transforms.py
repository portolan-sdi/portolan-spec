# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown==3.11.3", "pymdown-extensions==13.1", "pyyaml==6.0.3", "tinycss2==1.5.1", "pypdf==7.1.0", "markdown-it-py==4.3.0"]
# ///
"""Exercise build transforms and validator failures against HEAD or --ref."""

import argparse
import contextlib
import io
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import yaml
from pypdf import PdfWriter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build  # noqa: E402
import check_site  # noqa: E402


def fails(call, message):
    try:
        call()
    except ValueError as error:
        assert message in str(error), str(error)
    else:
        assert False, f"Expected failure containing {message}"


def check_links():
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp)
        (tree / "stac/examples").mkdir(parents=True)
        (tree / "stac/json-schema/v0.1.2").mkdir(parents=True)
        (tree / "stac/json-schema/schema.json").write_text("{}")
        mapping = {
            "README.md": "index.md",
            "stac/README.md": "stac/index.md",
            "specs/core.md": "specs/core.md",
        }

        def resolve(value, **options):
            return build.resolve_link(
                value, "stac/README.md", mapping, tree, "v0.2.0", True, **options
            )

        text = (
            "[Home](../README.md#intro) [Core](../specs/core.md#links) [Files](examples/)\n"
            "[Schema](json-schema/v0.1.2/schema.json#properties)\n"
            "[Data][data] [`script`](check.py)\n[data]: examples/a.json#field\n"
            '[script]: <check.py> "Title"\n'
            "`[code](check.py)` and ``[code](check.py) `literal` ``\n"
            '```md id="sample"\n[fenced](check.py)\n```\n'
        )
        output = build.rewrite_links(text, resolve)
        assert "[Home](../index.md#intro)" in output
        assert "[Core](../specs/core.md#links)" in output
        assert "tree/v0.2.0/stac/examples" in output
        assert (
            "https://schemas.portolan-sdi.org/portolan/v0.1.2/schema.json#properties"
            in output
        )
        assert (
            "[data]: https://github.com/portolan-sdi/portolan-spec/blob/v0.2.0/stac/examples/a.json#field"
            in output
        )
        assert (
            '[script]: <https://github.com/portolan-sdi/portolan-spec/blob/v0.2.0/stac/check.py> "Title"'
            in output
        )
        assert (
            "[`script`](https://github.com/portolan-sdi/portolan-spec/blob/v0.2.0/stac/check.py)"
            in output
        )
        assert "`[code](check.py)`" in output
        assert "``[code](check.py) `literal` ``" in output
        assert "[fenced](check.py)" in output
        assert '```md id="sample"' in output
        assert resolve("#local") == "#local"
        assert resolve("https://example.org/a#b") == "https://example.org/a#b"
        assert resolve("//example.org/a") == "//example.org/a"
        assert resolve("../stac/") == "index.md"
        assert (
            resolve("json-schema/schema.json")
            == "https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json"
        )
        assert resolve("json-schema/").endswith("/tree/v0.2.0/stac/json-schema")
        assert resolve("json-schema/v0.1.2/").endswith(
            "/tree/v0.2.0/stac/json-schema/v0.1.2"
        )
        assert resolve("json-schema/notes.txt").endswith(
            "/blob/v0.2.0/stac/json-schema/notes.txt"
        )
        draft = build.resolve_link(
            "json-schema/v0.2.0/schema.json",
            "stac/README.md",
            mapping,
            tree,
            "a" * 40,
            False,
        )
        assert f"/blob/{'a' * 40}/stac/json-schema/" in draft
        assert build.rewrite_links("[x](../requirements.yaml#one)", resolve).endswith(
            "/requirements.yaml#one)"
        )
        # Indented examples and inline backtick spans are not document links.
        indented = (
            'Before.\n\n    [code](check.py)\n    <img src="missing.png">\n\nAfter.\n'
        )
        assert build.rewrite_links(indented, resolve) == indented
        inline = "```[inline](check.py)``` and [real](check.py)\n[after](check.py)\n"
        rewritten = build.rewrite_links(inline, resolve)
        assert rewritten.startswith("```[inline](check.py)```")
        assert (
            "[real](https://github.com/" in rewritten
            and "[after](https://github.com/" in rewritten
        )
        assert build.normalize_fences(inline) == inline
        # CommonMark list continuations and nested items remain prose.
        list_mapping = {**mapping, "specs/portolan/core.md": "specs/portolan/core.md"}

        def list_resolve(value, **options):
            return build.resolve_link(
                value,
                "specs/portolan/core.md",
                list_mapping,
                tree,
                "v0.2.0",
                True,
                **options,
            )

        continuation = "1. Item\n\n    See [home](../../README.md)"
        assert (
            build.rewrite_links(continuation, list_resolve)
            == "1. Item\n\n    See [home](../../index.md)"
        )
        nested = "- Parent\n\n    - Child [home](../../README.md)\n\n        See [home](../../README.md)\n\n            [code](../keep.py)\n"
        rewritten = build.rewrite_links(nested, list_resolve)
        assert rewritten.count("[home](../../index.md)") == 2
        assert "            [code](../keep.py)" in rewritten
        # Raw HTML supports quoted and unquoted attributes, internal pages, and images.
        raw = '<a href="../specs/core.md#links">Core</a> <img src="examples/map.png"> <a href=check.py>x</a>'
        rewritten = build.rewrite_links(raw, resolve)
        assert 'href="../specs/core/#links"' in rewritten
        assert (
            'src="https://raw.githubusercontent.com/portolan-sdi/portolan-spec/v0.2.0/stac/examples/map.png"'
            in rewritten
        )
        assert (
            'href="https://github.com/portolan-sdi/portolan-spec/blob/v0.2.0/stac/check.py"'
            in rewritten
        )
        raw_map = "https://raw.githubusercontent.com/portolan-sdi/portolan-spec/v0.2.0/stac/examples/map.png"
        assert raw_map in build.rewrite_links("![map](examples/map.png)", resolve)
        assert raw_map in build.rewrite_links(
            "![map][image]\n\n[image]: examples/map.png", resolve
        )
        assert (
            resolve(
                "https://github.com/portolan-sdi/portolan-spec/blob/v0.2.0/stac/examples/map.png",
                image=True,
            )
            == raw_map
        )
        fails(
            lambda: resolve("../../escape.md"),
            "stac/README.md: link climbs above repository root: ../../escape.md",
        )
        fails(
            lambda: resolve("%2e%2e/%2e%2e/escape.md"), "climbs above repository root"
        )


def check_fences():
    text = '```yaml id="j49h8x"\na: 1\n```\n\n~~~python title="a"\nprint(1)\n~~~\n'
    assert (
        build.normalize_fences(text)
        == "```yaml\na: 1\n```\n\n~~~python\nprint(1)\n~~~\n"
    )
    assert (
        build.normalize_fences('````md id="x"\n```nested\n````\n')
        == "````md\n```nested\n````\n"
    )
    assert build.normalize_fences("```\na\n```\n") == "```\na\n```\n"
    assert (
        build.normalize_fences("    ```yaml id=x\n    a: 1\n    ```\n")
        == "    ```yaml id=x\n    a: 1\n    ```\n"
    )
    assert (
        build.normalize_fences(
            '1. Item\n\n    ```yaml id="sample"\n    a: 1\n    ```\n'
        )
        == "1. Item\n\n    ```yaml\n    a: 1\n    ```\n"
    )


def check_requirements(ref):
    baseline = yaml.safe_load(
        (build.ROOT / "specs/portolan/requirements.yaml").read_text()
    )
    floor = len(baseline["requirements"])
    manifest = yaml.safe_load(
        build.git("show", f"{ref}:specs/portolan/requirements.yaml")
    )
    resolved = set()
    for entry in manifest["requirements"]:
        text = build.git("show", f"{ref}:{entry['file']}")
        anchor = build.quote_section(text, entry["quote"])
        assert anchor in {heading["id"] for heading in build.toc(text)}, entry["id"]
        resolved.add(entry["id"])
    assert len(resolved) >= floor, (
        f"Expected at least {floor} requirement sections from the checkout manifest"
    )
    print(f"OK: {ref} has {len(resolved)} requirement sections; checkout floor {floor}")
    sample = "# Title\n\n## A `code` heading\n\nA sentence\nwith space.\n\n## A `code` heading\n\nOther text.\n"
    assert build.quote_section(sample, "A sentence with   space.") == "a-code-heading"
    assert build.quote_section(sample, "Other text.") == "a-code-heading_1"
    fails(lambda: build.quote_section(sample, "Missing quote"), "quote not found")
    # Check that section links belong to the same metadata line as each requirement.
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp)
        (tree / "specs/portolan").mkdir(parents=True)
        (tree / "specs/portolan/core.md").write_text(sample)
        (tree / "specs/portolan/requirements.yaml").write_text(
            yaml.safe_dump(
                {
                    "requirements": [
                        {
                            "id": "PORTO-CORE-001",
                            "severity": "MUST",
                            "enforcement": "validator",
                            "file": "specs/portolan/core.md",
                            "quote": "A sentence with space.",
                        }
                    ]
                }
            )
        )
        page, _ = build.requirements_page(
            tree, {"specs/portolan/core.md": "specs/portolan/core.md"}, "HEAD", False
        )
        assert (
            "Severity: **MUST** · Enforcement: **validator** · Section: [A code heading](specs/portolan/core.md#a-code-heading)"
            in page
        )
        assert "Specification section" not in page
        assert page.index("Section:") < page.index("> A sentence")


def check_banner():
    assert build.draft_title("0.3.0", "v0.2.0") == "Draft of v0.3.0"
    assert build.draft_title("0.2.0", "v0.2.0") == "Unreleased changes after v0.2.0"
    assert build.draft_title("0.2.0", "v0.02.0") == "Unreleased changes after v0.02.0"
    assert build.draft_title("0.1.0", "v0.2.0") == "Unreleased changes after v0.2.0"
    assert (
        build.draft_title("0.3.0-beta.1", "v0.3.0") == "Unreleased changes after v0.3.0"
    )
    text = build.draft_banner("0.3.0", "v0.2.0")
    assert text.startswith('!!! warning "Draft of v0.3.0"\n\n    ')
    assert (
        "This text is not released." in text
        and "https://spec.portolan-sdi.org/v0.2.0/" in text
    )
    rendered = build.markdown.markdown(text, extensions=build.MD_EXTENSIONS)
    assert '<p class="admonition-title">Draft of v0.3.0</p>' in rendered
    no_release = build.draft_banner("0.3.0", None)
    assert "/None/" not in no_release and "[the newest release]" not in no_release
    assert "Read " not in no_release


def check_navigation():
    mapping = {
        "README.md": "index.md",
        "specs/portolan/core.md": "specs/portolan/core.md",
        "specs/portolan/formats.md": "specs/portolan/formats.md",
        "specs/best-practices/README.md": "specs/best-practices/index.md",
        "specs/best-practices/styling.md": "specs/best-practices/styling.md",
        "specs/incubating/README.md": "specs/incubating/index.md",
        "specs/incubating/point-cloud.md": "specs/incubating/point-cloud.md",
        "specs/incubating/stac-geoparquet.md": "specs/incubating/stac-geoparquet.md",
        "specs/incubating/geotiff-stats-headers.md": "specs/incubating/geotiff-stats-headers.md",
    }
    headings = {
        "specs/incubating/stac-geoparquet.md": "Incubating — STAC-GeoParquet Beyond Raster Items",
        "specs/incubating/geotiff-stats-headers.md": "Incubating — GeoTIFF Statistics Headers",
        "specs/best-practices/index.md": "Best Practices",
    }
    nav = build.navigation(mapping, "next", headings)
    # Every entry is a group, because each top-level group collapses in the sidebar.
    assert all(isinstance(next(iter(item.values())), list) for item in nav)
    groups = [next(iter(item)) for item in nav]
    assert groups == [
        "Specification",
        "Best practices",
        "Incubating",
        "Project",
        "Downloads",
    ]
    pages = [
        page
        for item in nav
        for entries in item.values()
        for entry in entries
        for page in entry.values()
    ]
    # A reader meets the normative text first.
    assert pages[:3] == [
        "specs/portolan/core.md",
        "specs/portolan/formats.md",
        "requirements.md",
    ]
    assert nav[1]["Best practices"][0] == {"Overview": "specs/best-practices/index.md"}
    # A page without a heading falls back to its file name.
    assert {"Point cloud": "specs/incubating/point-cloud.md"} in nav[2]["Incubating"]
    # A page with an H1 takes the sentence-cased name after the group prefix.
    assert {
        "STAC-GeoParquet beyond raster items": "specs/incubating/stac-geoparquet.md"
    } in nav[2]["Incubating"]
    assert {
        "GeoTIFF statistics headers": "specs/incubating/geotiff-stats-headers.md"
    } in nav[2]["Incubating"]
    for heading, label in [
        ("Best Practices — Git-Backed Catalogs", "Git-backed catalogs"),
        ("Best Practices — The Grader", "Grader"),
        ("Conversion Defaults", "Conversion defaults"),
        (
            "Incubating — Apache Iceberg tables over published GeoParquet",
            "Apache Iceberg tables over published GeoParquet",
        ),
        ("COG and PMTiles Outputs", "COG and PMTiles outputs"),
    ]:
        assert build.nav_label(heading) == label, (heading, build.nav_label(heading))
    assert (
        build.page_heading(
            "Intro\n\n```\n# not a heading\n```\n\n# Real &amp; `code`\n"
        )
        == "Real & code"
    )
    assert nav[3]["Project"][0] == {"Overview": "index.md"}
    assert nav[4]["Downloads"] == [
        {"PDF": "downloads/portolan-spec-next.pdf"},
        {"EPUB": "downloads/portolan-spec-next.epub"},
    ]
    assert sorted(set(mapping.values()) - set(pages)) == []


def check_tags():
    with patch.object(
        build,
        "git",
        return_value="v0.1.2\nv0.2.0\nv0.10.0\nv0.3.0\nv9.0.0-rc.1\nv3.0\nv2.0.0+build.1",
    ):
        notice = io.StringIO()
        with contextlib.redirect_stdout(notice):
            assert build.releases() == ["v0.2.0", "v0.3.0", "v0.10.0"]
        for skipped in ("v9.0.0-rc.1", "v3.0", "v2.0.0+build.1"):
            assert f"Skip tag {skipped}" in notice.getvalue()


def check_output_guards():
    for path in (
        build.ROOT,
        build.ROOT / "site",
        build.ROOT / "specs/output",
        build.ROOT / "stac",
        build.ROOT / "examples",
    ):
        fails(lambda: build.output_root(path), "Refuse --out inside the source tree")
    assert build.output_root(build.ROOT / "_site") == build.ROOT / "_site"
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp)
        fails(lambda: build.require_build_marker(path), "missing build-info.json")
        (path / "keep.txt").write_text("keep")
        (path / "latest").mkdir()
        (path / "latest/keep.txt").write_text("keep alias")
        fails(lambda: build.alias_redirects(path, "v0.2.0"), "missing build-info.json")
        assert (path / "latest/keep.txt").read_text() == "keep alias"
        (path / "latest/build-info.json").write_text("{}")
        assert (path / "keep.txt").read_text() == "keep"
        (path / "build-info.json").write_text("{}")
        build.require_build_marker(path)
        link = path / "symlink"
        link.symlink_to(path, target_is_directory=True)
        fails(lambda: build.require_build_marker(link), "Refuse output symlink")
        (path / "v0.2.0/specs/core").mkdir(parents=True)
        (path / "v0.2.0/specs/core/index.html").write_text("core")
        (path / "v0.2.0/index.html").write_text("home")
        build.alias_redirects(path, "v0.2.0")
        redirect = (path / "latest/specs/core/index.html").read_text()
        assert "../../../v0.2.0/specs/core/" in redirect
        assert (
            "window.location.search" in redirect and "window.location.hash" in redirect
        )
        assert check_site.alias_errors(path, "v0.2.0") == []
        build.alias_redirects(path, "v0.2.0")  # A marked output can be rebuilt.


def check_fragment_targets():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "specs/core").mkdir(parents=True)
        target = root / "specs/core/index.html"
        target.write_text('<h2 id="assets">Assets</h2>')
        home = root / "index.html"
        original = '<a href="specs/core/?a=1&amp;b=2#assets">Assets</a>'
        home.write_text(original)
        assert (
            check_site.local_target(root, home, "specs/core/?a=1&b=2#assets") == target
        )
        assert check_site.local_target(root, home, "/specs/core/#assets") == target
        assert "assets" in check_site.Document(target.read_text()).ids
        assert home.read_text() == original


def check_root_guards():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        fresh = build.prepare_output_root(root / "fresh")
        assert (
            json.loads((fresh / build.ROOT_MARKER_NAME).read_text())
            == build.ROOT_MARKER
        )
        (fresh / "index.html").write_text("generated")
        assert build.prepare_output_root(fresh) == fresh
        empty = root / "empty"
        empty.mkdir()
        assert build.prepare_output_root(empty) == empty
        unowned = root / "unowned"
        unowned.mkdir()
        for name in ("index.html", "404.html", "versions.json"):
            (unowned / name).write_text(f"keep {name}")
        before = {p.name: p.read_bytes() for p in unowned.iterdir()}
        fails(lambda: build.prepare_output_root(unowned), "root build marker")
        with (
            patch.object(build, "toolchain"),
            patch.object(build, "fonts") as font_download,
            patch.object(
                sys, "argv", ["site/build.py", "--all", "--out", str(unowned)]
            ),
        ):
            with contextlib.redirect_stderr(io.StringIO()):
                assert build.main() == 1
            font_download.assert_not_called()
        assert {p.name: p.read_bytes() for p in unowned.iterdir()} == before
        marker = unowned / build.ROOT_MARKER_NAME
        for invalid in (
            "not JSON",
            "{}",
            json.dumps({"generator": "other-tool", "format": 1}),
        ):
            marker.write_text(invalid)
            fails(lambda: build.prepare_output_root(unowned), "root build marker")
        marker.unlink()
        marker.symlink_to(fresh / build.ROOT_MARKER_NAME)
        fails(lambda: build.prepare_output_root(unowned), "root build marker")


def check_main_selection():
    with tempfile.TemporaryDirectory() as tmp, patch.object(build, "ROOT", Path(tmp)):

        def git(*args):
            return subprocess.check_output(["git", "-C", tmp, *args], text=True).strip()

        git("init", "-q")
        git("config", "user.name", "Site test")
        git("config", "user.email", "site-test@example.org")
        git("symbolic-ref", "HEAD", "refs/heads/test")
        git("commit", "--allow-empty", "-qm", "test: base")
        base = git("rev-parse", "HEAD")
        fails(build.main_ref, "Neither main nor origin/main exists")
        git("update-ref", "refs/remotes/origin/main", base)
        assert build.main_ref() == "origin/main"  # CI often has no local main.
        git("update-ref", "refs/heads/main", base)
        assert build.main_ref() == "origin/main"
        git("commit", "--allow-empty", "-qm", "test: local descendant")
        child = git("rev-parse", "HEAD")
        git("update-ref", "refs/heads/main", child)
        assert build.main_ref() == "main"
        git("update-ref", "refs/remotes/origin/main", child)
        git("update-ref", "refs/heads/main", base)
        assert build.main_ref() == "origin/main"
        git("reset", "--soft", base)
        git("commit", "--allow-empty", "-qm", "test: divergent descendant")
        git("update-ref", "refs/heads/main", git("rev-parse", "HEAD"))
        fails(build.main_ref, "main and origin/main diverge")
        git("update-ref", "-d", "refs/remotes/origin/main")
        assert build.main_ref() == "main"


def check_validator_failures():
    colors = [
        "#fff",
        "#12345678",
        "rgb(1, 2, 3)",
        "rgba(1, 2, 3, 0.5)",
        "hsl(1 2% 3%)",
        "hsla(1, 2%, 3%, 0.5)",
        "hwb(1 2% 3%)",
        "lab(1 2 3)",
        "lch(1 2 3)",
        "oklch(1 2 3)",
        "oklab(1 2 3)",
        "color(srgb 1 0 0)",
        "red",
        "RebeccaPurple",
        "LightGoldenRodYellow",
        "papayawhip",
    ]
    for color in colors:
        for property_name in (
            "fill",
            "stroke",
            "box-shadow",
            "--custom-token",
            "border",
            "background",
        ):
            assert check_site.literal_colors(f"a {{ {property_name}: {color}; }}"), (
                property_name,
                color,
            )
    assert check_site.literal_colors("@media print { a { box-shadow: 0 0 2px red; } }")
    assert check_site.literal_colors("a { fill: var(--color-text, red); }")
    assert not check_site.literal_colors(
        'a { content: "red #fff"; background: url("red.png"); fill: var(--color-text); color: currentColor; border-color: transparent; stroke: inherit; --a: initial; --b: unset; }'
    )
    assert (
        check_site.github_error(
            "https://github.com/portolan-sdi/portolan-spec/blob/HEAD/README.md"
        )
        is None
    )
    assert (
        check_site.github_error(
            "https://github.com/portolan-sdi/portolan-spec/tree/HEAD/specs"
        )
        is None
    )
    assert check_site.github_error(
        "https://github.com/portolan-sdi/portolan-spec/blob/HEAD/no-such-file.txt"
    )
    assert check_site.github_error(
        "https://github.com/portolan-sdi/portolan-spec/tree/HEAD/README.md"
    )
    assert check_site.github_error(
        "https://raw.githubusercontent.com/portolan-sdi/portolan-spec/HEAD/no-such-image.png"
    )
    assert check_site.Document('<img src="missing.png"><img>').images == [
        "missing.png",
        "",
    ]
    with tempfile.TemporaryDirectory() as tmp:
        pdf = Path(tmp) / "short.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=100, height=100)
        writer.write(pdf)
        errors = check_site.pdf_errors(pdf, ["PORTO-FIRST-001", "PORTO-LAST-999"])
        assert any("more than 20 pages" in error for error in errors)
        assert any("PORTO-FIRST-001" in error for error in errors)
        assert any("PORTO-LAST-999" in error for error in errors)


def check_html_validator_failures():
    """Exercise whole-site HTML checks while isolated PDF/EPUB tests cover books."""
    manifest = yaml.safe_load(
        build.git("show", "HEAD:specs/portolan/requirements.yaml")
    )
    package = json.loads(build.git("show", "HEAD:stac/package.json"))["version"]
    tags = check_site.release_tags()
    latest = tags[0] if tags else None
    banner = build.markdown.markdown(
        build.draft_banner(package, latest), extensions=build.MD_EXTENSIONS
    )
    styles = (
        '<link rel="stylesheet" href="/next/assets/stylesheets/_brand-vars.css">'
        '<link rel="stylesheet" href="/next/assets/stylesheets/extra.css">'
    )
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "next"
        (root / "requirements").mkdir(parents=True)
        (root / "downloads").mkdir()
        shutil.copytree(build.SITE / "assets/stylesheets", root / "assets/stylesheets")
        # An incorrect metadata version must not affect the banner oracle.
        (root / "build-info.json").write_text(
            json.dumps({"ref": "HEAD", "version": "9999.0.0"})
        )
        identifiers = [entry["id"] for entry in manifest["requirements"]]
        (root / "requirements.json").write_text(
            json.dumps([{"id": value} for value in identifiers])
        )
        (root / "requirements/index.html").write_text(
            styles
            + banner
            + "".join(f'<h2 id="{value.lower()}">{value}</h2>' for value in identifiers)
        )
        (root / "downloads/portolan-spec-next.pdf").write_bytes(b"%PDFfixture")
        (root / "downloads/portolan-spec-next.epub").write_bytes(b"fixture")
        home = root / "index.html"
        valid = styles + banner + '<a href="">Home</a>'
        with (
            patch.object(check_site, "pdf_errors", return_value=[]),
            patch.object(check_site, "epub_errors", return_value=[]),
        ):
            home.write_text(valid)
            assert check_site.check(root) == []
            (root / "specs/core").mkdir(parents=True)
            (root / "specs/core/index.html").write_text(
                styles + banner + '<h2 id="assets">Assets</h2>'
            )
            home.write_text(valid + '<a href="specs/core/#assets">Assets</a>')
            assert check_site.check(root) == []
            assert 'href="specs/core/#assets"' in home.read_text()
            home.write_text(valid + '<a href="specs/core/#missing">Missing</a>')
            assert any(
                "missing local anchor" in error for error in check_site.check(root)
            )
            home.write_text(
                valid + '<a href="specs/core/index.html#assets">Noncanonical</a>'
            )
            assert any(
                "non-canonical page URL" in error for error in check_site.check(root)
            )
            home.write_text(valid + '<img src="missing.png">')
            assert any(
                "missing local href or src missing.png" in error
                for error in check_site.check(root)
            )
            home.write_text(valid + "<img>")
            assert any("image has no src" in error for error in check_site.check(root))
            home.write_text(valid + '<img src="../../outside.png">')
            assert any("leaves the site" in error for error in check_site.check(root))
            home.write_text(
                valid
                + '<a href="https://github.com/portolan-sdi/portolan-spec/blob/HEAD/no-such-file.txt">Bad</a>'
            )
            assert any("Missing Git blob" in error for error in check_site.check(root))
            home.write_text(
                styles
                + '<p class="admonition-title">Draft of v9999.0.0</p>This text is not released.'
            )
            assert any(
                "incorrect draft banner" in error for error in check_site.check(root)
            )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="HEAD")
    args = parser.parse_args()
    check_links()
    check_fences()
    check_requirements(args.ref)
    check_banner()
    check_navigation()
    check_tags()
    check_output_guards()
    check_root_guards()
    check_main_selection()
    check_fragment_targets()
    check_validator_failures()
    check_html_validator_failures()
    print(
        "OK: Markdown, requirement sections, banners, tags, aliases, guards, ancestry, and validator failures"
    )
