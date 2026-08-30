# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.3",
# ]
# ///
"""Check the committed language trees against the manifest that builds them.

Reads the manifest and its locale overlays, so a new locale or a new node needs
no edit here. Two things are checked. The trees must be structurally consistent
with each other, and every translated string must equal the overlay it comes
from, which is what catches a tree that was committed without a rebuild.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import yaml


REPO = Path(__file__).resolve().parent.parent.parent.parent
MANIFEST = REPO / "examples/manifests/portolan-reference.yaml"
ROOT = REPO / "examples/catalog/portolan-reference"
LANGUAGE_EXT = "https://stac-extensions.github.io/language/v1.0.0/schema.json"
ASSET_ROLES = ("data", "visual", "thumbnail", "source", "metadata", "style")


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text())


def _locales(manifest: dict) -> dict[str, dict]:
    locale_dir = MANIFEST.with_name(f"{MANIFEST.stem}.locales")
    return {
        code: yaml.safe_load((locale_dir / f"{code}.yaml").read_text())
        for code in manifest.get("translations") or []
    }


def _node_paths(manifest: dict) -> list[Path]:
    paths = [Path("catalog.json")]
    paths += [Path(key) / "catalog.json" for key in manifest["catalogs"]]
    paths += [Path(spec["id"]) / "collection.json" for spec in manifest["collections"]]
    return paths


def _metadata(locale: dict, path: Path) -> dict:
    if path == Path("catalog.json"):
        return locale["catalog"]
    key = path.parent.as_posix()
    section = "catalogs" if path.name == "catalog.json" else "collections"
    return locale[section][key]


def _path(code: str, source_code: str, relative: Path) -> Path:
    return ROOT / relative if code == source_code else ROOT / code / relative


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


def _asset_role(asset: dict) -> str:
    roles = asset.get("roles") or []
    for role in ASSET_ROLES:
        if role in roles:
            return role
    return "other"


def check_language_trees() -> None:
    manifest = _manifest()
    locales = _locales(manifest)
    translation_codes = manifest.get("translations") or []
    source_code = (manifest.get("language") or {}).get("code")
    languages = [source_code, *translation_codes] if source_code else []
    suffixes = tuple(
        part for code in translation_codes for part in (f"_{code}", f":{code}")
    )
    relatives = _node_paths(manifest)

    on_disk = sorted(
        path.relative_to(ROOT) for name in ("catalog.json", "collection.json")
        for path in ROOT.rglob(name)
        if path.relative_to(ROOT).parts[0] not in set(translation_codes)
    )
    assert on_disk == sorted(relatives), (
        f"the source tree does not match the manifest. "
        f"Extra: {sorted(set(on_disk) - set(relatives))}. "
        f"Missing: {sorted(set(relatives) - set(on_disk))}."
    )

    if not translation_codes:
        for relative in relatives:
            path = ROOT / relative
            obj = _load(path)
            assert LANGUAGE_EXT not in obj.get("stac_extensions", []), path
            assert "language" not in obj, path
            assert "languages" not in obj, path
            for link in obj.get("links", []):
                if link.get("rel") in ("agents", "describedby"):
                    assert "hreflang" not in link, path
        return

    language_objects = {
        source_code: manifest["language"],
        **{code: locale["language"] for code, locale in locales.items()},
    }

    for relative in relatives:
        source = _load(ROOT / relative)
        for code in languages:
            path = _path(code, source_code, relative)
            assert path.is_file(), f"missing {path}"
            obj = _load(path)
            declared = manifest["language"] if code == source_code \
                else locales[code]["language"]
            assert obj["stac_version"] == "1.1.0", path
            assert LANGUAGE_EXT in obj["stac_extensions"], path
            assert obj["language"] == declared, path
            assert obj["languages"] == [
                language_objects[other] for other in languages if other != code
            ], path
            assert obj["id"] == source["id"], path
            assert obj["type"] == source["type"], path
            assert not any(key.endswith(suffixes) for key in _keys(obj)), (
                f"language-suffixed metadata found in {path}"
            )

            alternates = [link for link in obj["links"] if link["rel"] == "alternate"]
            assert {link["hreflang"] for link in alternates} == set(languages) - {code}
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
                target_code = link["hreflang"]
                expected_title = (
                    language_objects[target_code].get("alternate")
                    or language_objects[target_code]["name"]
                    if code == source_code
                    else locales[code]["messages"]["language_names"][target_code]
                )
                assert link["title"] == expected_title, (
                    f"stale alternate title in {path}, {target_code}"
                )

            for link in (link for link in obj["links"] if link["rel"] == "child"):
                target = (path.parent / link["href"]).resolve()
                assert link["title"] == _load(target)["title"], (
                    f"stale child title in {path}: {link['href']}"
                )

            for rel in ("agents", "describedby"):
                link = next(link for link in obj["links"] if link["rel"] == rel)
                assert link["hreflang"] == code, path
                assert (path.parent / link["href"]).is_file(), path

            if code == source_code:
                continue
            assert path.with_name("README.md").read_text().startswith(f"# {obj['title']}\n")
            assert path.with_name("AGENTS.md").is_file(), path
            for asset in obj.get("assets", {}).values():
                if not _local(asset["href"]):
                    continue
                target = (path.parent / asset["href"]).resolve()
                assert target.is_file(), f"broken asset in {path}: {asset['href']}"
                assert ROOT / code not in target.parents, (
                    f"duplicated asset in {code}: {target}"
                )


def check_translations_match_their_overlay() -> None:
    """Every translated string must equal the overlay the build reads.

    Without this a hand-edited overlay stays green until somebody rebuilds, and
    the committed tree quietly disagrees with the manifest that owns it.
    """
    manifest = _manifest()
    locales = _locales(manifest)
    source_code = manifest["language"]["code"]
    for code, locale in locales.items():
        messages = locale["messages"]
        for relative in _node_paths(manifest):
            path = _path(code, source_code, relative)
            obj = _load(path)
            meta = _metadata(locale, relative)
            assert obj["title"] == meta["title"], f"stale title in {path}"
            assert obj["description"] == meta["description"].strip(), (
                f"stale description in {path}"
            )
            if obj["type"] == "Collection":
                assert obj.get("keywords", []) == meta.get("keywords", []), (
                    f"stale keywords in {path}"
                )
                actual_columns = {
                    column["name"]: column["description"]
                    for column in obj.get("table:columns", [])
                    if column.get("description")
                }
                assert actual_columns == (meta.get("columns") or {}), (
                    f"stale column descriptions in {path}"
                )
            overrides = meta.get("assets") or {}
            for key, asset in obj.get("assets", {}).items():
                expected = overrides.get(key) or messages["asset_titles"][
                    _asset_role(asset)
                ]
                assert asset["title"] == expected, (
                    f"stale asset title in {path}, {key}: "
                    f"{asset['title']!r} is not {expected!r}"
                )
            titles = [asset["title"] for asset in obj.get("assets", {}).values()]
            assert len(titles) == len(set(titles)), (
                f"two assets share one title in {path}: {sorted(titles)}"
            )
            for link in obj["links"]:
                rel = link["rel"]
                if rel in ("alternate", "child") or "title" not in link:
                    continue
                assert link["title"] == messages["link_titles"][rel], (
                    f"stale link title in {path}, rel {rel}"
                )


def check_translation_trees_hold_metadata_only() -> None:
    manifest = _manifest()
    allowed = {".json", ".md"}
    for code in manifest.get("translations") or []:
        unexpected = [
            path
            for path in (ROOT / code).rglob("*")
            if path.is_file() and path.suffix not in allowed
        ]
        assert not unexpected, f"translated tree contains data files: {unexpected}"


CHECKS = [
    check_language_trees,
    check_translations_match_their_overlay,
    check_translation_trees_hold_metadata_only,
]


def main() -> int:
    for check in CHECKS:
        check()
        print(f"PASS {check.__name__}")
    print("all multilingual checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
