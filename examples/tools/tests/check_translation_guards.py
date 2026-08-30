# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.3",
# ]
# ///
"""Exercise translation-generator guards against isolated failing inputs."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import yaml


TOOLS = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOLS))

from config import LANGUAGE_EXT  # noqa: E402
from translations import ASSET_ROLES, REQUIRED_MESSAGES, build_translations  # noqa: E402


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def _source(kind: str = "Catalog", **extra) -> dict:
    value = {
        "type": kind,
        "stac_version": "1.1.0",
        "stac_extensions": ["portolan", LANGUAGE_EXT],
        "id": "sample",
        "title": "Sample",
        "description": "Sample.",
        "language": {"code": "en", "name": "English"},
        "languages": [{"code": "ja", "name": "日本語"}],
        "links": [],
    }
    value.update(extra)
    return value


def _messages(link_titles: dict | None = None) -> dict:
    messages = {key: key for key in REQUIRED_MESSAGES}
    messages["link_titles"] = link_titles or {}
    messages["asset_titles"] = {
        role: role for role in (*ASSET_ROLES, "other")
    }
    messages["language_names"] = {"en": "English"}
    return messages


def _locale(
    *,
    link_titles: dict | None = None,
    catalogs: dict | None = None,
    collections: dict | None = None,
) -> dict:
    return {
        "language": {"code": "ar", "name": "العربية", "dir": "rtl"},
        "messages": _messages(link_titles),
        "catalog": {"title": "عينة", "description": "عينة."},
        "catalogs": catalogs or {},
        "collections": collections or {},
    }


def _case(manifest: dict, locale: dict | None = None):
    stack = tempfile.TemporaryDirectory()
    root = Path(stack.name)
    out = root / "catalog"
    manifest_path = root / "sample.yaml"
    manifest_path.write_text(yaml.safe_dump(manifest, allow_unicode=True))
    if locale is not None:
        locale_dir = root / "sample.locales"
        locale_dir.mkdir()
        (locale_dir / "ar.yaml").write_text(
            yaml.safe_dump(locale, allow_unicode=True)
        )
    return stack, out, manifest_path


def _expect_value_error(call, text: str) -> None:
    try:
        call()
    except ValueError as error:
        assert text in str(error), error
    else:
        raise AssertionError(f"expected ValueError containing {text!r}")


def check_zero_locales_clear_only_generated_language_state() -> None:
    manifest = {
        "language": {"code": "en", "name": "English"},
        "translations": [],
        "catalogs": {},
        "collections": [],
    }
    stack, out, path = _case(manifest)
    with stack:
        source = _source(links=[
            {
                "rel": "alternate", "href": "./ja/catalog.json",
                "type": "application/json", "hreflang": "ja",
            },
            {
                "rel": "alternate", "href": "https://example.com/fr.json",
                "type": "application/json", "hreflang": "fr",
            },
            {"rel": "agents", "href": "./AGENTS.md", "hreflang": "en"},
        ])
        _write_json(out / "catalog.json", source)
        _write_json(out / "ja/catalog.json", {"language": {"code": "ja"}})
        build_translations(manifest, path, out)
        result = json.loads((out / "catalog.json").read_text())
        assert not (out / "ja").exists()
        assert LANGUAGE_EXT not in result["stac_extensions"]
        assert "language" not in result and "languages" not in result
        assert [link["href"] for link in result["links"] if link["rel"] == "alternate"] == [
            "https://example.com/fr.json"
        ]
        assert result["links"][-1] == {"rel": "agents", "href": "./AGENTS.md"}


def check_invalid_links_do_not_prune() -> None:
    manifest = {
        "language": {"code": "en", "name": "English"},
        "translations": ["ar"], "catalogs": {}, "collections": [],
    }
    stack, out, path = _case(manifest, _locale(link_titles={"unused": "x"}))
    with stack:
        _write_json(out / "catalog.json", _source())
        _write_json(out / "ja/catalog.json", {"language": {"code": "ja"}})
        _expect_value_error(
            lambda: build_translations(manifest, path, out), "Unused: unused"
        )
        assert (out / "ja").is_dir()


def check_duplicate_codes_do_not_prune() -> None:
    manifest = {
        "language": {"code": "en", "name": "English"},
        "translations": ["ar", "ar"], "catalogs": {}, "collections": [],
    }
    stack, out, path = _case(manifest, _locale())
    with stack:
        _write_json(out / "catalog.json", _source())
        _write_json(out / "ja/catalog.json", {"language": {"code": "ja"}})
        _expect_value_error(
            lambda: build_translations(manifest, path, out),
            "language codes must be unique",
        )
        assert (out / "ja").is_dir()


def check_directory_collision_preserves_source() -> None:
    manifest = {
        "language": {"code": "en", "name": "English"},
        "translations": ["ar"], "catalogs": {"ar": {}}, "collections": [],
    }
    stack, out, path = _case(manifest)
    with stack:
        _write_json(out / "catalog.json", _source())
        _write_json(out / "ar/catalog.json", {"type": "Catalog"})
        _expect_value_error(
            lambda: build_translations(manifest, path, out), "collides"
        )
        assert (out / "ar/catalog.json").is_file()


def _column_case(columns: dict):
    manifest = {
        "language": {"code": "en", "name": "English"},
        "translations": ["ar"],
        "catalogs": {"group": {}},
        "collections": [{"id": "group/item"}],
    }
    locale = _locale(
        catalogs={"group": {"title": "مجموعة", "description": "مجموعة."}},
        collections={
            "group/item": {
                "title": "عنصر", "description": "عنصر.", "columns": columns,
            }
        },
    )
    stack, out, path = _case(manifest, locale)
    _write_json(out / "catalog.json", _source())
    _write_json(out / "group/catalog.json", _source(id="group"))
    _write_json(out / "group/item/collection.json", _source(
        "Collection", id="item",
        **{"table:columns": [{"name": "code", "description": "Code."}]},
    ))
    return stack, out, path, manifest


def check_missing_column_fails() -> None:
    stack, out, path, manifest = _column_case({})
    with stack:
        _expect_value_error(
            lambda: build_translations(manifest, path, out), "Missing: code"
        )


def check_unknown_column_fails() -> None:
    stack, out, path, manifest = _column_case({"code": "الرمز.", "ghost": "x"})
    with stack:
        _expect_value_error(
            lambda: build_translations(manifest, path, out), "Unknown: ghost"
        )


CHECKS = [
    check_zero_locales_clear_only_generated_language_state,
    check_invalid_links_do_not_prune,
    check_duplicate_codes_do_not_prune,
    check_directory_collision_preserves_source,
    check_missing_column_fails,
    check_unknown_column_fails,
]


def main() -> int:
    for check in CHECKS:
        check()
        print(f"PASS {check.__name__}")
    print("all translation guard checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
