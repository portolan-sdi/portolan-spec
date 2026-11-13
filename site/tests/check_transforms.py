# /// script
# requires-python = ">=3.12"
# dependencies = ["markdown==3.11.3", "pymdown-extensions==13.1", "pyyaml==6.0.3"]
# ///
"""Exercise staging transforms and all requirements in the main Git tree."""

import sys
import tempfile
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build  # noqa: E402


def check_links():
    with tempfile.TemporaryDirectory() as tmp:
        tree = Path(tmp)
        (tree / "stac/examples").mkdir(parents=True)
        mapping = {
            "README.md": "index.md",
            "stac/README.md": "stac/index.md",
            "specs/core.md": "specs/core.md",
        }

        def resolve(value):
            return build.resolve_link(
                value, "stac/README.md", mapping, tree, "v0.2.0", True
            )

        text = (
            "[Home](../README.md#intro) [Core](../specs/core.md#links) [Files](examples/)\n"
            "[Schema](json-schema/v0.2.0/schema.json#properties)\n"
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
            "https://schemas.portolan-sdi.org/portolan/v0.2.0/schema.json#properties"
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


def check_requirements():
    for ref in dict.fromkeys(["main", build.main_ref()]):
        manifest = yaml.safe_load(
            build.git("show", f"{ref}:specs/portolan/requirements.yaml")
        )
        assert len(manifest["requirements"]) >= 135, (
            "The main census must cover the baseline"
        )
        for entry in manifest["requirements"]:
            text = build.git("show", f"{ref}:{entry['file']}")
            anchor = build.quote_section(text, entry["quote"])
            assert anchor in {heading["id"] for heading in build.toc(text)}, entry["id"]
        print(f"OK: {ref} has {len(manifest['requirements'])} requirement sections")
    sample = "# Title\n\n## A `code` heading\n\nA sentence\nwith space.\n\n## A `code` heading\n\nOther text.\n"
    assert build.quote_section(sample, "A sentence with   space.") == "a-code-heading"
    assert build.quote_section(sample, "Other text.") == "a-code-heading_1"
    try:
        build.quote_section(sample, "Missing quote")
    except ValueError:
        pass
    else:
        assert False, "A missing quote must fail"


def check_semver():
    tags = [
        "v0.2.0",
        "v0.2.1",
        "v0.3.0-alpha",
        "v0.3.0-alpha.1",
        "v0.3.0-alpha.2",
        "v0.3.0-alpha.10",
        "v0.3.0-beta",
        "v0.3.0-rc.1",
        "v0.3.0",
        "v0.10.0",
        "v1.0.0",
    ]
    assert sorted(reversed(tags), key=build.semver_key) == tags
    assert build.semver_key("v1.0.0+build.2") == build.semver_key("v1.0.0")
    assert build.semver_key("v01.0.0") is None
    assert build.semver_key("v1.0.0-01") is None
    assert build.semver_key("version-one") is None


def check_banner():
    text = build.draft_banner("0.3.0", "v0.2.0")
    assert text.startswith('!!! warning "Draft of v0.3.0"\n\n    ')
    assert "This text is not released." in text
    assert "https://spec.portolan-sdi.org/v0.2.0/" in text
    rendered = build.markdown.markdown(text, extensions=build.MD_EXTENSIONS)
    assert '<div class="admonition warning">' in rendered
    assert '<p class="admonition-title">Draft of v0.3.0</p>' in rendered


if __name__ == "__main__":
    check_links()
    check_fences()
    check_requirements()
    check_banner()
    check_semver()
    print(
        "OK: link transforms, fences, all main requirement sections, and draft banner"
    )
