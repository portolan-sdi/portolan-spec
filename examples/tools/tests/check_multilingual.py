# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.3",
# ]
# ///
"""Check the committed language trees against the manifest that builds them.

Discovers each manifest that declares translations. A new catalog, locale, or
node needs no test edit. The checks compare each tree with its source manifest
and locale overlays. This comparison detects a tree that lacks a rebuild.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

import yaml


REPO = Path(__file__).resolve().parent.parent.parent.parent
MANIFESTS = REPO / "examples/manifests"
CATALOGS = REPO / "examples/catalog"
LANGUAGE_EXT = "https://stac-extensions.github.io/language/v1.0.0/schema.json"
ASSET_ROLES = ("data", "visual", "thumbnail", "source", "metadata", "style")


def _load(path: Path) -> dict:
    return json.loads(path.read_text())


def _translation_cases() -> list[tuple[Path, Path, dict, dict[str, dict]]]:
    paths = sorted((*MANIFESTS.glob("*.yaml"), *MANIFESTS.glob("*.yml")))
    cases = []
    for manifest_path in paths:
        manifest = yaml.safe_load(manifest_path.read_text())
        if not manifest.get("translations"):
            continue
        root = CATALOGS / manifest_path.stem
        locales = _locales(manifest_path, manifest)
        cases.append((manifest_path, root, manifest, locales))
    return cases


def _locales(manifest_path: Path, manifest: dict) -> dict[str, dict]:
    locale_dir = manifest_path.with_name(f"{manifest_path.stem}.locales")
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


def _path(root: Path, code: str, source_code: str, relative: Path) -> Path:
    return root / relative if code == source_code else root / code / relative


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


def _check_language_tree(root: Path, manifest: dict, locales: dict[str, dict]) -> None:
    translation_codes = manifest.get("translations") or []
    source_code = (manifest.get("language") or {}).get("code")
    languages = [source_code, *translation_codes] if source_code else []
    suffixes = tuple(
        part for code in translation_codes for part in (f"_{code}", f":{code}")
    )
    relatives = _node_paths(manifest)

    on_disk = sorted(
        path.relative_to(root) for name in ("catalog.json", "collection.json")
        for path in root.rglob(name)
        if path.relative_to(root).parts[0] not in set(translation_codes)
    )
    assert on_disk == sorted(relatives), (
        f"the source tree does not match the manifest. "
        f"Extra: {sorted(set(on_disk) - set(relatives))}. "
        f"Missing: {sorted(set(relatives) - set(on_disk))}."
    )

    if not translation_codes:
        for relative in relatives:
            path = root / relative
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
        source = _load(root / relative)
        for code in languages:
            path = _path(root, code, source_code, relative)
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
                assert link["title"] == expected_title.strip(), (
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
                assert root / code not in target.parents, (
                    f"duplicated asset in {code}: {target}"
                )


def check_language_trees() -> None:
    cases = _translation_cases()
    assert cases, "no example manifest declares translations"
    for _, root, manifest, locales in cases:
        _check_language_tree(root, manifest, locales)


def _check_translations_match_overlay(
    root: Path, manifest: dict, locales: dict[str, dict]
) -> None:
    """Every translated string must equal the overlay the build reads.

    Without this a hand-edited overlay stays green until somebody rebuilds, and
    the committed tree quietly disagrees with the manifest that owns it.
    """
    source_code = manifest["language"]["code"]
    for code, locale in locales.items():
        messages = locale["messages"]
        for relative in _node_paths(manifest):
            path = _path(root, code, source_code, relative)
            obj = _load(path)
            source = _load(root / relative)
            meta = _metadata(locale, relative)
            assert obj["title"] == meta["title"].strip(), f"stale title in {path}"
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
                expected_columns = {
                    name: description.strip()
                    for name, description in (meta.get("columns") or {}).items()
                }
                assert actual_columns == expected_columns, (
                    f"stale column descriptions in {path}"
                )
            overrides = meta.get("assets") or {}
            for key, asset in obj.get("assets", {}).items():
                override = overrides.get(key) or {}
                expected = override.get("title") or messages["asset_titles"][
                    _asset_role(asset)
                ]
                assert asset["title"] == expected.strip(), (
                    f"stale asset title in {path}, {key}: "
                    f"{asset['title']!r} is not {expected!r}"
                )
                source_asset = source.get("assets", {})[key]
                if "description" in source_asset:
                    expected_description = override["description"].strip()
                    assert asset.get("description") == expected_description, (
                        f"stale asset description in {path}, {key}"
                    )
                else:
                    assert "description" not in asset, (
                        f"unexpected asset description in {path}, {key}"
                    )
            titles = [asset["title"] for asset in obj.get("assets", {}).values()]
            assert len(titles) == len(set(titles)), (
                f"two assets share one title in {path}: {sorted(titles)}"
            )
            source_links = [
                link for link in source["links"] if link["rel"] != "alternate"
            ]
            translated_links = [
                link for link in obj["links"] if link["rel"] != "alternate"
            ]
            assert len(source_links) == len(translated_links), path
            for source_link, link in zip(source_links, translated_links, strict=True):
                rel = link["rel"]
                if rel in ("alternate", "child") or "title" not in link:
                    continue
                link_override = (
                    (meta.get("links") or {}).get(rel) or {}
                ).get(source_link["href"])
                expected_title = link_override or messages["link_titles"][rel]
                assert link["title"] == expected_title.strip(), (
                    f"stale link title in {path}, rel {rel}"
                )


def check_translations_match_their_overlay() -> None:
    cases = _translation_cases()
    assert cases, "no example manifest declares translations"
    for _, root, manifest, locales in cases:
        _check_translations_match_overlay(root, manifest, locales)


def check_translation_trees_hold_metadata_only() -> None:
    allowed = {".json", ".md"}
    cases = _translation_cases()
    assert cases, "no example manifest declares translations"
    for _, root, manifest, _ in cases:
        for code in manifest.get("translations") or []:
            unexpected = [
                path
                for path in (root / code).rglob("*")
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
