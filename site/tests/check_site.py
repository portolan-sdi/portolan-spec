# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml==6.0.3"]
# ///
"""Validate one version directory or a complete site, without network access."""

from __future__ import annotations

import json
import posixpath
import re
import subprocess
import sys
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

ROOT = Path(__file__).resolve().parents[2]


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.hrefs = []
        self.styles = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if "href" in attributes:
            self.hrefs.append(attributes["href"])
        if tag == "link" and attributes.get("rel") == "stylesheet":
            self.styles.append(attributes.get("href", ""))


def epub_errors(path: Path) -> list[str]:
    errors = []
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if (
            not entries
            or entries[0].filename != "mimetype"
            or archive.read("mimetype") != b"application/epub+zip"
        ):
            errors.append(f"{path}: invalid first EPUB entry")
        elif entries[0].compress_type != zipfile.ZIP_STORED:
            errors.append(f"{path}: EPUB mimetype must be uncompressed")
        documents = {
            name: Document(archive.read(name).decode())
            for name in archive.namelist()
            if name.endswith(".xhtml")
        }
        for name, document in documents.items():
            for href in document.hrefs:
                parts = urlsplit(href)
                if parts.scheme or parts.netloc:
                    continue
                target = (
                    posixpath.normpath(
                        posixpath.join(posixpath.dirname(name), unquote(parts.path))
                    )
                    if parts.path
                    else name
                )
                if target not in archive.namelist():
                    errors.append(f"{path}:{name}: missing EPUB target {href}")
                elif (
                    parts.fragment
                    and target in documents
                    and unquote(parts.fragment) not in documents[target].ids
                ):
                    errors.append(f"{path}:{name}: missing EPUB anchor {href}")
    return errors


def check(directory: Path) -> list[str]:
    errors = []
    versions_file = directory / "versions.json"
    if versions_file.exists():
        versions = json.loads(versions_file.read_text())
        latest = [v for v in versions if "latest" in v["aliases"]]
        if len(latest) != 1 or latest[0]["version"] == "next":
            errors.append(
                "versions.json must give exactly one release the latest alias"
            )
        releases = [v["version"] for v in versions if v["version"] != "next"]
        if latest and (not releases or latest[0]["version"] != releases[-1]):
            errors.append("versions.json must give the final release the latest alias")
        if not any(
            v == {"version": "next", "title": "next (draft)", "aliases": []}
            for v in versions
        ):
            errors.append("versions.json must include next (draft)")
        if not (directory / "index.html").is_file():
            errors.append("Missing root redirect")
        elif (
            latest
            and f"url={latest[0]['version']}/"
            not in (directory / "index.html").read_text()
        ):
            errors.append("Root redirect does not point to latest")
        roots = [directory / v["version"] for v in versions]
    elif (directory / "build-info.json").is_file():
        roots = [directory]
    else:
        roots = [p.parent for p in directory.glob("*/build-info.json")]
    if not roots:
        return errors + [f"No built versions in {directory}"]
    # All local hrefs must stay within the supplied site root.
    boundary = directory.resolve()
    documents = {}
    for path in directory.rglob("*.html"):
        text = path.read_text()
        documents[path.resolve()] = Document(text)
        if "--8<--" in text:
            errors.append(f"{path}: unexpanded snippet marker")
    for root in roots:
        label = root.name
        if not (root / "index.html").is_file():
            errors.append(f"{label}: missing index.html")
            continue
        info = json.loads((root / "build-info.json").read_text())
        expected_draft = f"Draft of v{info['version']}"
        for path in root.rglob("*.html"):
            text = path.read_text()
            draft = re.search(r'class="admonition-title">Draft of v[^<]+', text)
            if label == "next" and (not draft or expected_draft not in draft[0]):
                errors.append(f"{path}: missing or incorrect draft banner")
            if label != "next" and draft:
                errors.append(f"{path}: released page has a draft banner")
            if label == "next" and "This text is not released." not in text:
                errors.append(f"{path}: missing draft notice")
        locations = json.loads((root / "requirements.json").read_text())
        manifest = yaml.safe_load(
            subprocess.check_output(
                [
                    "git",
                    "-C",
                    str(ROOT),
                    "show",
                    f"{info['ref']}:specs/portolan/requirements.yaml",
                ],
                text=True,
            )
        )
        expected = {entry["id"] for entry in manifest["requirements"]}
        if {location["id"] for location in locations} != expected:
            errors.append(f"{label}: requirements differ from the archived manifest")
        requirements = documents.get((root / "requirements/index.html").resolve())
        if not requirements:
            errors.append(f"{label}: missing requirements page")
        else:
            for identifier in expected:
                if identifier.lower() not in requirements.ids:
                    errors.append(
                        f"{label}: missing requirement anchor {identifier.lower()}"
                    )
        for extension in ("pdf", "epub"):
            path = root / "downloads" / f"portolan-spec-{label}.{extension}"
            if not path.is_file():
                errors.append(f"{label}: missing {extension}")
            elif extension == "pdf":
                with path.open("rb") as stream:
                    if stream.read(4) != b"%PDF":
                        errors.append(f"{path}: invalid PDF header")
            else:
                try:
                    errors.extend(epub_errors(path))
                except (zipfile.BadZipFile, KeyError) as error:
                    errors.append(f"{path}: {error}")
        css = root / "assets/stylesheets/extra.css"
        if not css.is_file():
            errors.append(f"{label}: missing extra.css")
        else:
            text = re.sub(r"/\*.*?\*/", "", css.read_text(), flags=re.DOTALL)
            if re.search(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|oklch|lab)\(", text):
                errors.append(f"{label}: extra.css has a literal color")
            for name, value in re.findall(r"([\w-]+)\s*:\s*([^;{}]+)", text):
                if "color" in name or name in {
                    "background",
                    "border",
                    "border-top",
                    "border-right",
                    "border-bottom",
                    "border-left",
                }:
                    remainder = re.sub(r"var\(--[\w-]+\)", "", value)
                    words = set(re.findall(r"[a-zA-Z][a-zA-Z-]*", remainder))
                    if words - {
                        "color-mix",
                        "in",
                        "srgb",
                        "transparent",
                        "solid",
                        "none",
                        "px",
                        "pt",
                        "rem",
                        "em",
                    }:
                        errors.append(
                            f"{label}: extra.css has a literal color in {name}"
                        )
            tokens = set(re.findall(r"var\((--[\w-]+)", text))
            brand = set(
                re.findall(
                    r"(--[\w-]+)\s*:", (css.parent / "_brand-vars.css").read_text()
                )
            )
            if tokens - brand:
                errors.append(
                    f"{label}: extra.css reads non-brand tokens: {tokens - brand}"
                )
        for path in root.rglob("*.html"):
            document = documents[path.resolve()]
            styles = document.styles
            brand = next(
                (
                    i
                    for i, value in enumerate(styles)
                    if value.endswith("/_brand-vars.css")
                ),
                None,
            )
            extra = next(
                (i for i, value in enumerate(styles) if value.endswith("/extra.css")),
                None,
            )
            if brand is None or extra is None or brand >= extra:
                errors.append(f"{path}: incorrect brand stylesheet order")
    for path, document in documents.items():
        for href in document.hrefs:
            parts = urlsplit(href)
            if parts.scheme or parts.netloc:
                continue
            if "stac/json-schema/" in unquote(parts.path):
                errors.append(f"{path}: relative schema link {href}")
            local_path = unquote(parts.path)
            if local_path.startswith("/"):
                if (directory / "build-info.json").is_file():
                    prefix = f"/{directory.name}/"
                    target = (
                        (directory / local_path.removeprefix(prefix)).resolve()
                        if local_path.startswith(prefix)
                        else Path(local_path)
                    )
                else:
                    target = (directory / local_path.lstrip("/")).resolve()
            else:
                target = (path.parent / local_path).resolve() if local_path else path
            if not target.is_relative_to(boundary):
                errors.append(f"{path}: href leaves the site: {href}")
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"{path}: missing local href {href}")
            elif (
                parts.fragment
                and target in documents
                and unquote(parts.fragment) not in documents[target].ids
            ):
                errors.append(f"{path}: missing local anchor {href}")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: uv run --script site/tests/check_site.py <dir>", file=sys.stderr)
        return 2
    try:
        errors = check(Path(sys.argv[1]).resolve())
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        errors = [str(error)]
    if errors:
        print("\n".join(errors), file=sys.stderr)
        print(f"FAIL: {len(errors)} site errors", file=sys.stderr)
        return 1
    print(
        "OK: requirements, versions, downloads, banners, local links, and brand styles"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
