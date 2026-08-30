"""Generate alternate-language STAC trees from locale overlay manifests.

This module owns the Language extension for the whole catalog. It writes the
`language` and `languages` fields, the `alternate` links, and one subtree per
declared locale. It also removes them again when a manifest drops a locale, so
a committed tree always matches the manifest that built it.
"""
from __future__ import annotations

from copy import deepcopy
import json
import os
import re
import shutil
from pathlib import Path
from urllib.parse import urlparse

import yaml

from config import LANGUAGE_EXT


JSON_TYPE = "application/json"
STRUCTURAL_RELS = frozenset({"root", "parent", "child"})
SIDECAR_RELS = frozenset({"agents", "describedby"})
# `child` takes its title from the target node and `alternate` from the locale
# it points at, so neither is translated through the `link_titles` table.
UNTRANSLATED_RELS = frozenset({"alternate", "child"})
# Asset roles in the order a title is chosen from, most specific first.
ASSET_ROLES = ("data", "visual", "thumbnail", "source", "metadata", "style")
# Directories the source tree owns at the root of a catalog, beside the group
# directories the manifest names.
RESERVED_DIRS = frozenset({"_assets"})
LOCALE_CODE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")
REQUIRED_MESSAGES = frozenset({
    "collections", "data_files", "license", "source", "last_synced",
    "detailed_english", "agent_heading", "agent_intro", "link_titles",
    "asset_titles", "crs_heading", "crs_note", "language_names",
})


def _has_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _relative_href(start: Path, target: Path) -> str:
    href = Path(os.path.relpath(target, start)).as_posix()
    return href if href.startswith("../") else f"./{href}"


def _is_local(href: str) -> bool:
    return not urlparse(href).scheme and not href.startswith("//")


def _node_paths(manifest: dict) -> list[Path]:
    paths = [Path("catalog.json")]
    paths += [Path(key) / "catalog.json" for key in manifest["catalogs"]]
    paths += [Path(spec["id"]) / "collection.json" for spec in manifest["collections"]]
    return paths


def _node_key(path: Path) -> tuple[str, str]:
    if path == Path("catalog.json"):
        return "catalog", "catalog"
    if path.name == "catalog.json":
        return "catalogs", path.parent.as_posix()
    return "collections", path.parent.as_posix()


def _metadata(locale: dict, path: Path) -> dict:
    section, key = _node_key(path)
    if section == "catalog":
        return locale["catalog"]
    return locale[section][key]


def _reserved_names(manifest: dict) -> set[str]:
    """Return the top-level directory names the source tree already owns."""
    names = set(RESERVED_DIRS) | set(manifest["catalogs"])
    names |= {Path(spec["id"]).parts[0] for spec in manifest["collections"]}
    return names


def _load_locales(manifest: dict, manifest_path: Path) -> list[dict]:
    codes = manifest.get("translations") or []
    if not codes:
        return []
    if not manifest.get("language"):
        raise ValueError("a manifest with translations must declare language")

    reserved = _reserved_names(manifest)
    locale_dir = manifest_path.with_suffix("")
    locale_dir = locale_dir.with_name(f"{locale_dir.name}.locales")
    locales = []
    for code in codes:
        if not isinstance(code, str) or not LOCALE_CODE.fullmatch(code):
            raise ValueError(f"invalid translation code: {code!r}")
        # A locale writes its whole tree to <out>/<code>, so a code that matches
        # a group directory would delete that group and the data under it.
        if code in reserved:
            raise ValueError(
                f"translation code {code!r} collides with the catalog directory "
                f"of the same name. Rename the catalog or drop the locale."
            )
        path = locale_dir / f"{code}.yaml"
        if not path.is_file():
            raise ValueError(f"translation overlay not found: {path}")
        locale = yaml.safe_load(path.read_text())
        actual = (locale.get("language") or {}).get("code")
        if actual != code:
            raise ValueError(f"{path} declares language {actual!r}, expected {code!r}")
        locale["_path"] = path
        locales.append(locale)
    _check_locale_coverage(manifest, locales)
    return locales


def _check_locale_coverage(manifest: dict, locales: list[dict]) -> None:
    catalog_ids = set(manifest["catalogs"])
    collection_ids = {spec["id"] for spec in manifest["collections"]}
    language_codes = {
        manifest["language"]["code"],
        *(locale["language"]["code"] for locale in locales),
    }
    for locale in locales:
        path = locale["_path"]
        if set(locale.get("catalogs") or {}) != catalog_ids:
            raise ValueError(f"{path} must translate every catalog ID")
        if set(locale.get("collections") or {}) != collection_ids:
            raise ValueError(f"{path} must translate every collection ID")
        missing = REQUIRED_MESSAGES - set(locale.get("messages") or {})
        if missing:
            raise ValueError(f"{path} lacks messages: {', '.join(sorted(missing))}")
        current_code = locale["language"]["code"]
        language_names = locale["messages"].get("language_names") or {}
        expected_names = language_codes - {current_code}
        if set(language_names) != expected_names:
            missing_names = ", ".join(sorted(expected_names - set(language_names))) or "none"
            unused_names = ", ".join(sorted(set(language_names) - expected_names)) or "none"
            raise ValueError(
                f"{path} language_names must name every other language. "
                f"Missing: {missing_names}. Unused: {unused_names}."
            )
        if any(not _has_text(value) for value in language_names.values()):
            raise ValueError(f"{path} has an empty language name")
        nodes = [locale.get("catalog")]
        nodes += list(locale["catalogs"].values())
        nodes += list(locale["collections"].values())
        for node in nodes:
            if (
                not node
                or not _has_text(node.get("title"))
                or not _has_text(node.get("description"))
            ):
                raise ValueError(f"{path} has a node without title or description")
        for spec in manifest["collections"]:
            translated = locale["collections"][spec["id"]]
            if spec.get("keywords") and not translated.get("keywords"):
                raise ValueError(f"{path} lacks keywords for {spec['id']}")


def _check_node_coverage(
    source_objects: dict[Path, dict], locales: list[dict]
) -> None:
    """Fail on any source prose an overlay cannot translate.

    The build reads the source tree it has already written, so this sees the
    exact links and assets that each locale must cover. A common relation or
    role supplies a title when it identifies one value. Per-node overrides
    distinguish duplicate relations and assets. Every source asset description
    needs a translated description.
    """
    titled_rels = {
        link["rel"] for obj in source_objects.values()
        for link in obj.get("links", [])
        if "title" in link and link.get("rel") not in UNTRANSLATED_RELS
    }
    ambiguous_assets: dict[Path, set[str]] = {}
    described_assets: dict[Path, set[str]] = {}
    ambiguous_links: dict[Path, set[tuple[str, str]]] = {}
    titled_links: dict[Path, set[tuple[str, str]]] = {}
    for path, obj in source_objects.items():
        by_role: dict[str, set[str]] = {}
        for key, asset in (obj.get("assets") or {}).items():
            by_role.setdefault(_asset_role(asset), set()).add(key)
        keys = {key for group in by_role.values() if len(group) > 1 for key in group}
        if keys:
            ambiguous_assets[path] = keys
        described = {
            key for key, asset in (obj.get("assets") or {}).items()
            if "description" in asset
        }
        if described:
            described_assets[path] = described

        by_rel: dict[str, list[str]] = {}
        pairs = set()
        for link in obj.get("links", []):
            rel = link.get("rel")
            if "title" not in link or rel in UNTRANSLATED_RELS:
                continue
            href = link.get("href", "")
            by_rel.setdefault(rel, []).append(href)
            pairs.add((rel, href))
        titled_links[path] = pairs
        duplicate_pairs = {
            (rel, href) for rel, hrefs in by_rel.items() if len(hrefs) > 1
            for href in hrefs
        }
        if duplicate_pairs:
            ambiguous_links[path] = duplicate_pairs

    for locale in locales:
        lp = locale["_path"]
        rels = set(locale["messages"]["link_titles"])
        if rels != titled_rels:
            missing = ", ".join(sorted(titled_rels - rels)) or "none"
            unused = ", ".join(sorted(rels - titled_rels)) or "none"
            raise ValueError(
                f"{lp} link_titles must name every link rel that carries a "
                f"title. Missing: {missing}. Unused: {unused}."
            )
        for path, obj in source_objects.items():
            meta = _metadata(locale, path)
            asset_overrides = meta.get("assets") or {}
            override_keys = set(asset_overrides)
            unknown_assets = override_keys - set(obj.get("assets") or {})
            if unknown_assets:
                raise ValueError(
                    f"{lp} names assets the node does not carry, "
                    f"{path.as_posix()}: {', '.join(sorted(unknown_assets))}"
                )
            for key, override in asset_overrides.items():
                if not isinstance(override, dict):
                    raise ValueError(
                        f"{lp} asset override must contain title or description, "
                        f"{path.as_posix()}: {key}"
                    )
                unknown_fields = set(override) - {"title", "description"}
                if unknown_fields:
                    raise ValueError(
                        f"{lp} asset override has unknown fields, "
                        f"{path.as_posix()}: {key}: "
                        f"{', '.join(sorted(unknown_fields))}"
                    )
                if any(not _has_text(value) for value in override.values()):
                    raise ValueError(
                        f"{lp} asset override has empty text, "
                        f"{path.as_posix()}: {key}"
                    )
            missing_titles = {
                key for key in ambiguous_assets.get(path, set())
                if not _has_text((asset_overrides.get(key) or {}).get("title"))
            }
            if missing_titles:
                raise ValueError(
                    f"{lp} must give a title to every asset that shares a role, "
                    f"{path.as_posix()}: {', '.join(sorted(missing_titles))}"
                )
            missing_descriptions = {
                key for key in described_assets.get(path, set())
                if not _has_text((asset_overrides.get(key) or {}).get("description"))
            }
            if missing_descriptions:
                raise ValueError(
                    f"{lp} must translate every asset description, "
                    f"{path.as_posix()}: {', '.join(sorted(missing_descriptions))}"
                )
            extra_descriptions = {
                key for key, override in asset_overrides.items()
                if "description" in override
                and key not in described_assets.get(path, set())
            }
            if extra_descriptions:
                raise ValueError(
                    f"{lp} describes assets without a source description, "
                    f"{path.as_posix()}: {', '.join(sorted(extra_descriptions))}"
                )

            link_overrides = meta.get("links") or {}
            override_pairs = set()
            for rel, links in link_overrides.items():
                if not isinstance(links, dict):
                    raise ValueError(
                        f"{lp} link override must map hrefs to titles, "
                        f"{path.as_posix()}: {rel}"
                    )
                for href, title in links.items():
                    override_pairs.add((rel, href))
                    if not _has_text(title):
                        raise ValueError(
                            f"{lp} link override has an empty title, "
                            f"{path.as_posix()}: {rel}: {href}"
                        )
            unknown_links = override_pairs - titled_links.get(path, set())
            if unknown_links:
                unknown_text = ", ".join(
                    f"{rel} {href}" for rel, href in sorted(unknown_links)
                )
                raise ValueError(
                    f"{lp} names titled links the node does not carry, "
                    f"{path.as_posix()}: {unknown_text}"
                )
            missing_links = ambiguous_links.get(path, set()) - override_pairs
            if missing_links:
                missing_text = ", ".join(
                    f"{rel} {href}" for rel, href in sorted(missing_links)
                )
                raise ValueError(
                    f"{lp} must give each repeated link relation a title, "
                    f"{path.as_posix()}: {missing_text}"
                )
            if obj.get("type") != "Collection":
                continue
            columns = obj.get("table:columns") or []
            described = {
                column["name"] for column in columns if column.get("description")
            }
            known = {column["name"] for column in columns}
            translated = meta.get("columns") or {}
            translated_names = set(translated)
            missing_columns = described - translated_names
            unknown_columns = translated_names - known
            if missing_columns or unknown_columns:
                missing_text = ", ".join(sorted(missing_columns)) or "none"
                unknown_text = ", ".join(sorted(unknown_columns)) or "none"
                raise ValueError(
                    f"{lp} columns must translate every described column in "
                    f"{path.as_posix()}. Missing: {missing_text}. "
                    f"Unknown: {unknown_text}."
                )
            if any(not _has_text(value) for value in translated.values()):
                raise ValueError(
                    f"{lp} has an empty column description in {path.as_posix()}"
                )


def _language_objects(manifest: dict, locales: list[dict]) -> dict[str, dict]:
    objects = [manifest["language"]] + [locale["language"] for locale in locales]
    by_code = {obj["code"]: dict(obj) for obj in objects}
    if len(by_code) != len(objects):
        raise ValueError("language codes must be unique")
    return by_code


def _set_language_fields(obj: dict, code: str, languages: dict[str, dict]) -> None:
    extensions = obj.setdefault("stac_extensions", [])
    if LANGUAGE_EXT not in extensions:
        extensions.append(LANGUAGE_EXT)
    obj["language"] = dict(languages[code])
    obj["languages"] = [dict(value) for key, value in languages.items() if key != code]


def _strip_generated_links(
    obj: dict, current_path: Path, relative_path: Path, out: Path
) -> list[dict]:
    """Drop every `alternate` link this module wrote on an earlier build.

    Match the exact local href this module generated for each previously declared
    language. Preserve authored alternates, including external language links.
    """
    previous_codes = {
        language.get("code") for language in obj.get("languages", [])
        if language.get("code")
    }
    generated = {
        (code, _relative_href(current_path.parent, out / code / relative_path))
        for code in previous_codes
    }
    return [
        dict(link) for link in obj.get("links", [])
        if not (
            link.get("rel") == "alternate"
            and (link.get("hreflang"), link.get("href")) in generated
        )
    ]


def _alternate_links(
    current_path: Path,
    relative_path: Path,
    current_code: str,
    source_code: str,
    languages: dict[str, dict],
    language_titles: dict[str, str],
    out: Path,
) -> list[dict]:
    links = []
    for code in languages:
        if code == current_code:
            continue
        target = out / relative_path if code == source_code else out / code / relative_path
        links.append({
            "rel": "alternate",
            "href": _relative_href(current_path.parent, target),
            "type": JSON_TYPE,
            "title": language_titles[code].strip(),
            "hreflang": code,
        })
    return links


def _asset_role(asset: dict) -> str:
    roles = asset.get("roles") or []
    for role in ASSET_ROLES:
        if role in roles:
            return role
    return "other"


def _asset_title(key: str, asset: dict, messages: dict, overrides: dict) -> str:
    """Return the translated title of one asset.

    A per-key title in the overlay wins. Without one the role carries the
    title, which reads correctly only while the role is unique in the node.
    `_check_node_coverage` rejects an overlay that leans on a role two assets
    share.
    """
    override = overrides.get(key) or {}
    title = override.get("title") or messages["asset_titles"][_asset_role(asset)]
    return title.strip()


def _link_title(
    rel: str, href: str, messages: dict, overrides: dict
) -> str:
    title = (overrides.get(rel) or {}).get(href)
    return (title or messages["link_titles"][rel]).strip()


def _localize_object(
    source: dict,
    source_node: Path,
    target_node: Path,
    relative_path: Path,
    code: str,
    source_code: str,
    locale: dict,
    languages: dict[str, dict],
    all_titles: dict[str, dict[Path, str]],
    language_titles: dict[str, str],
    out: Path,
) -> dict:
    obj = deepcopy(source)
    meta = _metadata(locale, relative_path)
    messages = locale["messages"]
    obj["title"] = meta["title"].strip()
    obj["description"] = meta["description"].strip()
    if obj["type"] == "Collection":
        obj["keywords"] = meta.get("keywords", [])
        overrides = meta.get("assets") or {}
        column_overrides = meta.get("columns") or {}
        for column in obj.get("table:columns", []):
            if column.get("description"):
                column["description"] = column_overrides[column["name"]].strip()
        for key, asset in obj.get("assets", {}).items():
            href = asset.get("href", "")
            if _is_local(href):
                target = (source_node.parent / href).resolve()
                asset["href"] = _relative_href(target_node.parent, target)
            asset["title"] = _asset_title(key, asset, messages, overrides)
            if "description" in asset:
                asset["description"] = overrides[key]["description"].strip()

    links = []
    for source_link in source.get("links", []):
        if source_link.get("rel") == "alternate":
            continue
        localized = dict(source_link)
        rel = localized.get("rel")
        href = localized.get("href", "")
        if rel in SIDECAR_RELS:
            localized["hreflang"] = code
        elif rel not in STRUCTURAL_RELS and _is_local(href):
            target = (source_node.parent / href).resolve()
            localized["href"] = _relative_href(target_node.parent, target)
        if rel == "child":
            child_source = (source_node.parent / href).resolve()
            child_rel = child_source.relative_to(out.resolve())
            localized["title"] = all_titles[code][child_rel]
        elif "title" in localized:
            localized["title"] = _link_title(
                rel, href, messages, meta.get("links") or {}
            )
        links.append(localized)
    links += _alternate_links(
        target_node, relative_path, code, source_code, languages,
        language_titles, out
    )
    obj["links"] = links
    _set_language_fields(obj, code, languages)
    return obj


def _english_sidecar_href(target_node: Path, source_node: Path, name: str) -> str:
    return _relative_href(target_node.parent, source_node.with_name(name))


def _crs_lines(source: dict, messages: dict) -> list[str]:
    """Return the CRS section of a localized AGENTS.md.

    The code comes from the `data` asset, so the section cannot drift from the
    data. The full explanation stays in the English AGENTS.md, which the reader
    reaches through the link at the end of the file.
    """
    code = ((source.get("assets") or {}).get("data") or {}).get("proj:code")
    if not code:
        return []
    return ["", f"## {messages['crs_heading']}", "", code, "", messages["crs_note"]]


def _write_sidecars(
    obj: dict,
    source: dict,
    target_node: Path,
    source_node: Path,
    locale: dict,
) -> None:
    messages = locale["messages"]
    lines = [f"# {obj['title']}", "", obj["description"], ""]
    if obj["type"] == "Catalog":
        children = [link for link in obj["links"] if link.get("rel") == "child"]
        lines += [f"## {messages['collections']}", ""]
        lines += [
            f"- [{link['title']}]({Path(link['href']).parent.as_posix()}/README.md)"
            for link in children
        ]
    else:
        lines += [f"## {messages['data_files']}", ""]
        for asset in obj.get("assets", {}).values():
            lines.append(f"- [{asset['title']}]({asset['href']})")
        lines += [
            "",
            f"## {messages['license']}",
            "",
            source["license"],
        ]
        source_link = next(
            (link for link in source["links"] if link.get("rel") == "via"), None
        )
        if source_link:
            lines += [
                "",
                f"## {messages['source']}",
                "",
                f"[{messages['source']}]({source_link['href']})",
            ]
        if source.get("updated"):
            lines += [
                "",
                f"## {messages['last_synced']}",
                "",
                source["updated"],
            ]
    english_readme = _english_sidecar_href(target_node, source_node, "README.md")
    lines += ["", f"[{messages['detailed_english']}]({english_readme})", ""]
    target_node.with_name("README.md").write_text("\n".join(lines))

    english_agents = _english_sidecar_href(target_node, source_node, "AGENTS.md")
    agent_lines = [
        f"# {messages['agent_heading']}: {obj['title']}",
        "",
        messages["agent_intro"],
    ]
    agent_lines += _crs_lines(source, messages)
    agent_lines += ["", f"[{messages['detailed_english']}]({english_agents})", ""]
    target_node.with_name("AGENTS.md").write_text("\n".join(agent_lines))


def _write_json(path: Path, obj: dict) -> None:
    """Write a node, and leave the file alone when nothing changed."""
    text = json.dumps(obj, ensure_ascii=False, indent=2) + "\n"
    if not path.is_file() or path.read_text() != text:
        path.write_text(text)


def _prune_stale_locales(out: Path, manifest: dict, keep: set[str]) -> None:
    """Delete a locale tree the manifest no longer declares.

    A directory is a locale tree only when its own `catalog.json` declares the
    language the directory is named for. That test never matches a group
    directory of the source tree, so a wrong manifest cannot delete data.
    """
    if not out.is_dir():
        return
    reserved = _reserved_names(manifest)
    for child in sorted(out.iterdir()):
        name = child.name
        if not child.is_dir() or name in keep or name in reserved:
            continue
        if not LOCALE_CODE.fullmatch(name):
            continue
        node = child / "catalog.json"
        if not node.is_file():
            continue
        try:
            obj = json.loads(node.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            continue
        if (obj.get("language") or {}).get("code") == name:
            shutil.rmtree(child)


def _clear_language_fields(out: Path, paths: list[Path]) -> None:
    """Return the source tree to the state a build without locales writes."""
    for path in paths:
        node = out / path
        if not node.is_file():
            continue
        obj = json.loads(node.read_text())
        source_code = (obj.get("language") or {}).get("code")
        links = []
        for link in _strip_generated_links(obj, node, path, out):
            if (link.get("rel") in SIDECAR_RELS
                    and link.get("hreflang") == source_code):
                link.pop("hreflang", None)
            links.append(link)
        obj["links"] = links
        obj.pop("language", None)
        obj.pop("languages", None)
        obj["stac_extensions"] = [
            ext for ext in obj.get("stac_extensions", []) if ext != LANGUAGE_EXT
        ]
        _write_json(node, obj)


def build_translations(manifest: dict, manifest_path: Path, out: Path) -> None:
    """Update the source tree and generate every declared language tree."""
    locales = _load_locales(manifest, manifest_path)
    paths = _node_paths(manifest)
    keep = {locale["language"]["code"] for locale in locales}
    if manifest.get("language"):
        keep.add(manifest["language"]["code"])
    source_objects = {path: json.loads((out / path).read_text()) for path in paths}
    if not locales:
        _prune_stale_locales(out, manifest, keep)
        _clear_language_fields(out, paths)
        return
    source_code = manifest["language"]["code"]
    languages = _language_objects(manifest, locales)
    _check_node_coverage(source_objects, locales)
    _prune_stale_locales(out, manifest, keep)

    locale_by_code = {locale["language"]["code"]: locale for locale in locales}
    all_titles: dict[str, dict[Path, str]] = {
        source_code: {path: source_objects[path]["title"] for path in paths}
    }
    for code, locale in locale_by_code.items():
        all_titles[code] = {
            path: _metadata(locale, path)["title"].strip() for path in paths
        }

    for path, source in source_objects.items():
        obj = deepcopy(source)
        links = _strip_generated_links(obj, out / path, path, out)
        for link in links:
            if link.get("rel") in SIDECAR_RELS:
                link["hreflang"] = source_code
        links += _alternate_links(
            out / path, path, source_code, source_code, languages,
            {
                code: language.get("alternate") or language["name"]
                for code, language in languages.items() if code != source_code
            },
            out,
        )
        obj["links"] = links
        _set_language_fields(obj, source_code, languages)
        _write_json(out / path, obj)

    for code, locale in locale_by_code.items():
        locale_root = out / code
        if locale_root.exists():
            shutil.rmtree(locale_root)
        for path in paths:
            source_node = out / path
            target_node = locale_root / path
            target_node.parent.mkdir(parents=True, exist_ok=True)
            obj = _localize_object(
                source_objects[path],
                source_node,
                target_node,
                path,
                code,
                source_code,
                locale,
                languages,
                all_titles,
                locale["messages"]["language_names"],
                out,
            )
            _write_json(target_node, obj)
            _write_sidecars(obj, source_objects[path], target_node, source_node, locale)
