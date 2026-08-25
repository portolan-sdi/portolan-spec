# /// script
# requires-python = ">=3.12"
# ///
"""Check the committed English, Arabic, and Japanese STAC trees."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse


REPO = Path(__file__).resolve().parent.parent.parent.parent
ROOT = REPO / "examples/catalog/portolan-reference"
LANGUAGE_EXT = "https://stac-extensions.github.io/language/v1.0.0/schema.json"
LANGUAGES = ("en", "ar", "ja")


def _source_nodes() -> list[Path]:
    nodes = []
    for name in ("catalog.json", "collection.json"):
        nodes += [
            path for path in ROOT.rglob(name)
            if path.relative_to(ROOT).parts[0] not in {"ar", "ja"}
        ]
    return sorted(nodes)


def _path(code: str, relative: Path) -> Path:
    return ROOT / relative if code == "en" else ROOT / code / relative


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _local(href: str) -> bool:
    return not urlparse(href).scheme and not href.startswith("//")


def _keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _keys(child)


def check_language_trees() -> None:
    source_nodes = _source_nodes()
    assert len(source_nodes) == 14, f"expected 14 source nodes, found {len(source_nodes)}"

    for source_path in source_nodes:
        relative = source_path.relative_to(ROOT)
        source = _load(source_path)
        for code in LANGUAGES:
            path = _path(code, relative)
            assert path.is_file(), f"missing {path}"
            obj = _load(path)
            assert obj["stac_version"] == "1.1.0", path
            assert LANGUAGE_EXT in obj["stac_extensions"], path
            assert obj["language"]["code"] == code, path
            if code == "ar":
                assert obj["language"]["dir"] == "rtl", path
            assert {lang["code"] for lang in obj["languages"]} == set(LANGUAGES) - {code}
            assert obj["id"] == source["id"], path
            assert obj["type"] == source["type"], path
            assert not any(
                key.endswith(("_ar", "_ja", ":ar", ":ja")) for key in _keys(obj)
            ), f"language-suffixed metadata found in {path}"

            alternates = [link for link in obj["links"] if link["rel"] == "alternate"]
            assert {link["hreflang"] for link in alternates} == set(LANGUAGES) - {code}
            for link in obj["links"]:
                if _local(link["href"]):
                    assert (path.parent / link["href"]).resolve().is_file(), (
                        f"broken link in {path}: {link['href']}"
                    )
            for link in alternates:
                target = (path.parent / link["href"]).resolve()
                assert target.is_file(), f"broken alternate link in {path}: {link['href']}"
                alternate = _load(target)
                assert alternate["id"] == obj["id"], target
                assert alternate["type"] == obj["type"], target
                assert alternate["language"]["code"] == link["hreflang"], target

            for rel in ("agents", "describedby"):
                link = next(link for link in obj["links"] if link["rel"] == rel)
                assert link["hreflang"] == code, path
                assert (path.parent / link["href"]).is_file(), path

            if code != "en":
                assert path.with_name("README.md").read_text().startswith(f"# {obj['title']}\n")
                assert path.with_name("AGENTS.md").is_file(), path
                for asset in obj.get("assets", {}).values():
                    if not _local(asset["href"]):
                        continue
                    target = (path.parent / asset["href"]).resolve()
                    assert target.is_file(), f"broken asset in {path}: {asset['href']}"
                    assert ROOT / code not in target.parents, f"duplicated asset in {code}: {target}"


def check_translation_trees_hold_metadata_only() -> None:
    allowed = {".json", ".md"}
    for code in ("ar", "ja"):
        unexpected = [
            path
            for path in (ROOT / code).rglob("*")
            if path.is_file() and path.suffix not in allowed
        ]
        assert not unexpected, f"translated tree contains data files: {unexpected}"


CHECKS = [check_language_trees, check_translation_trees_hold_metadata_only]


def main() -> int:
    for check in CHECKS:
        check()
        print(f"PASS {check.__name__}")
    print("all multilingual checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
