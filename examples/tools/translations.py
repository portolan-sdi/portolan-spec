"""Generate alternate-language STAC trees from locale overlay manifests."""
from __future__ import annotations

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
LOCALE_CODE = re.compile(r"^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$")


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


def _load_locales(manifest: dict, manifest_path: Path) -> list[dict]:
    codes = manifest.get("translations") or []
    if not codes:
        return []
    if not manifest.get("language"):
        raise ValueError("a manifest with translations must declare language")

    locale_dir = manifest_path.with_suffix("")
    locale_dir = locale_dir.with_name(f"{locale_dir.name}.locales")
    locales = []
    for code in codes:
        if not isinstance(code, str) or not LOCALE_CODE.fullmatch(code):
            raise ValueError(f"invalid translation code: {code!r}")
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
    required_messages = {
        "collections", "data_files", "license", "source", "last_synced",
        "detailed_english", "agent_heading", "agent_intro", "link_titles",
        "asset_titles",
    }
    for locale in locales:
        path = locale["_path"]
        if set(locale.get("catalogs") or {}) != catalog_ids:
            raise ValueError(f"{path} must translate every catalog ID")
        if set(locale.get("collections") or {}) != collection_ids:
            raise ValueError(f"{path} must translate every collection ID")
        missing = required_messages - set(locale.get("messages") or {})
        if missing:
            raise ValueError(f"{path} lacks messages: {', '.join(sorted(missing))}")
        for node in [locale.get("catalog")] + list(locale["catalogs"].values()) + list(
            locale["collections"].values()
        ):
            if not node or not node.get("title") or not node.get("description"):
                raise ValueError(f"{path} has a node without title or description")
        for spec in manifest["collections"]:
            translated = locale["collections"][spec["id"]]
            if spec.get("keywords") and not translated.get("keywords"):
                raise ValueError(f"{path} lacks keywords for {spec['id']}")


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


def _alternate_links(
    current_path: Path,
    relative_path: Path,
    current_code: str,
    source_code: str,
    languages: dict[str, dict],
    titles: dict[str, dict[Path, str]],
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
            "title": titles[code][relative_path],
            "hreflang": code,
        })
    return links


def _asset_title(asset: dict, messages: dict) -> str:
    roles = asset.get("roles") or []
    titles = messages["asset_titles"]
    for role in ("data", "visual", "thumbnail", "source", "metadata", "style"):
        if role in roles:
            return titles[role]
    return titles["other"]


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
    out: Path,
) -> dict:
    obj = json.loads(json.dumps(source))
    meta = _metadata(locale, relative_path)
    messages = locale["messages"]
    obj["title"] = meta["title"]
    obj["description"] = meta["description"].strip()
    if obj["type"] == "Collection":
        obj["keywords"] = meta.get("keywords", [])
        for column in obj.get("table:columns", []):
            column.pop("description", None)
        for asset in obj.get("assets", {}).values():
            href = asset.get("href", "")
            if _is_local(href):
                target = (source_node.parent / href).resolve()
                asset["href"] = _relative_href(target_node.parent, target)
            asset["title"] = _asset_title(asset, messages)
            asset.pop("description", None)

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
        translated_title = messages["link_titles"].get(rel)
        if translated_title:
            localized["title"] = translated_title
        links.append(localized)
    links += _alternate_links(
        target_node, relative_path, code, source_code, languages, all_titles, out
    )
    obj["links"] = links
    _set_language_fields(obj, code, languages)
    return obj


def _english_sidecar_href(target_node: Path, source_node: Path, name: str) -> str:
    return _relative_href(target_node.parent, source_node.with_name(name))


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
        "",
        f"[{messages['detailed_english']}]({english_agents})",
        "",
    ]
    target_node.with_name("AGENTS.md").write_text("\n".join(agent_lines))


def build_translations(manifest: dict, manifest_path: Path, out: Path) -> None:
    """Update the source tree and generate every declared language tree."""
    locales = _load_locales(manifest, manifest_path)
    if not locales:
        return
    source_code = manifest["language"]["code"]
    languages = _language_objects(manifest, locales)
    paths = _node_paths(manifest)
    source_objects = {path: json.loads((out / path).read_text()) for path in paths}

    locale_by_code = {locale["language"]["code"]: locale for locale in locales}
    all_titles: dict[str, dict[Path, str]] = {
        source_code: {path: source_objects[path]["title"] for path in paths}
    }
    for code, locale in locale_by_code.items():
        all_titles[code] = {path: _metadata(locale, path)["title"] for path in paths}

    for path, obj in source_objects.items():
        links = [
            dict(link) for link in obj.get("links", [])
            if not (link.get("rel") == "alternate" and link.get("hreflang") in languages)
        ]
        for link in links:
            if link.get("rel") in SIDECAR_RELS:
                link["hreflang"] = source_code
        links += _alternate_links(
            out / path, path, source_code, source_code, languages, all_titles, out
        )
        obj["links"] = links
        _set_language_fields(obj, source_code, languages)
        (out / path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")

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
                out,
            )
            target_node.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n")
            _write_sidecars(obj, source_objects[path], target_node, source_node, locale)
