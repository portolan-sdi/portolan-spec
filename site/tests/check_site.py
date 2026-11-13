# /// script
# requires-python = ">=3.12"
# dependencies = ["pyyaml==6.0.3", "tinycss2==1.5.1", "pypdf==7.1.0"]
# ///
"""Validate one version directory or a complete site without network access."""

from __future__ import annotations

import json
import posixpath
import re
import subprocess
import sys
import zipfile
from functools import lru_cache
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import tinycss2
import yaml
from pypdf import PdfReader
from tinycss2.color4 import parse_color

ROOT = Path(__file__).resolve().parents[2]
COLOR_FUNCTIONS = {
    "rgb",
    "rgba",
    "hsl",
    "hsla",
    "hwb",
    "lab",
    "lch",
    "oklch",
    "oklab",
    "color",
}
COLOR_KEYWORDS_ALLOWED = {"transparent", "currentcolor", "inherit", "initial", "unset"}


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def release_tags():
    tags = [
        tag
        for tag in git("tag", "--list", "v*").splitlines()
        if re.fullmatch(r"v\d+\.\d+\.\d+", tag)
    ]
    return sorted(
        (tag for tag in tags if version_key(tag) >= (0, 2, 0)),
        key=version_key,
        reverse=True,
    )


def version_key(version):
    return tuple(map(int, version.removeprefix("v").split(".")))


def expected_draft_title(ref):
    # Read the archived package, independently of build-info's version field.
    version = json.loads(git("show", f"{ref}:stac/package.json"))["version"]
    tags = release_tags()
    latest = tags[0] if tags else None
    package = re.match(r"^(\d+)\.(\d+)\.(\d+)", version)
    if not package:
        raise ValueError(f"Invalid source package version at {ref}: {version}")
    if latest and tuple(map(int, package.groups())) <= version_key(latest):
        return f"Unreleased changes after {latest}", latest
    return f"Draft of v{version}", latest


class Document(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.ids = set()
        self.hrefs = []
        self.images = []
        self.styles = []
        self.banners = []
        self._banner = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if "id" in attributes:
            self.ids.add(attributes["id"])
        if "href" in attributes:
            self.hrefs.append(attributes["href"])
        if tag == "img":
            self.images.append(attributes.get("src", ""))
        if tag == "link" and attributes.get("rel") == "stylesheet":
            self.styles.append(attributes.get("href", ""))
        if tag == "p" and "admonition-title" in attributes.get("class", "").split():
            self._banner = True

    def handle_data(self, data):
        if self._banner:
            self.banners.append(data.strip())

    def handle_endtag(self, tag):
        if tag == "p":
            self._banner = False


def literal_colors(text: str) -> list[str]:
    """Inspect all declaration values, including nested rules and custom properties."""
    found = []

    def tokens(values):
        for token in values:
            if token.type == "function":
                if token.lower_name in COLOR_FUNCTIONS:
                    found.append(token.serialize())
                else:
                    tokens(token.arguments)
            elif token.type in {"ident", "hash"}:
                if (
                    token.type == "ident"
                    and token.lower_value in COLOR_KEYWORDS_ALLOWED
                ):
                    continue
                if parse_color(token) is not None:
                    found.append(token.serialize())
            elif hasattr(token, "content"):
                tokens(token.content)

    def rules(items):
        for item in items:
            if item.type == "declaration":
                tokens(item.value)
            elif (
                item.type in {"at-rule", "qualified-rule"} and item.content is not None
            ):
                rules(
                    tinycss2.parse_blocks_contents(
                        item.content, skip_comments=True, skip_whitespace=True
                    )
                )
            elif item.type == "error":
                raise ValueError(f"Invalid extra.css: {item.message}")

    rules(tinycss2.parse_stylesheet(text, skip_comments=True, skip_whitespace=True))
    return found


@lru_cache(maxsize=None)
def github_error(url: str) -> str | None:
    """Validate this repository's absolute source URLs against local Git objects."""
    parts = urlsplit(url)
    if parts.netloc == "github.com":
        match = re.fullmatch(
            r"/portolan-sdi/portolan-spec/(blob|tree)/([^/]+)/(.*)", unquote(parts.path)
        )
        if not match:
            return None
        kind, ref, path = match.groups()
    elif parts.netloc == "raw.githubusercontent.com":
        match = re.fullmatch(
            r"/portolan-sdi/portolan-spec/([^/]+)/(.*)", unquote(parts.path)
        )
        if not match:
            return None
        ref, path = match.groups()
        kind = "blob"
    else:
        return None
    path = path.rstrip("/")
    result = subprocess.run(
        ["git", "-C", str(ROOT), "cat-file", "-t", f"{ref}:{path}"],
        text=True,
        capture_output=True,
    )
    if result.returncode or result.stdout.strip() != kind:
        return f"Missing Git {kind} at {ref}:{path}: {url}"
    return None


def pdf_errors(path: Path, identifiers: list[str]) -> list[str]:
    errors = []
    with path.open("rb") as stream:
        if stream.read(4) != b"%PDF":
            return [f"{path}: invalid PDF header"]
    reader = PdfReader(path)
    if len(reader.pages) <= 20:
        errors.append(f"{path}: PDF must have more than 20 pages")
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    for identifier in (identifiers[0], identifiers[-1]):
        if identifier not in text:
            errors.append(f"{path}: missing PDF requirement {identifier}")
    return errors


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
            for href in document.hrefs + document.images:
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


def alias_errors(directory: Path, latest: str) -> list[str]:
    errors = []
    for canonical in (directory / latest).rglob("*.html"):
        alias = directory / "latest" / canonical.relative_to(directory / latest)
        expected = posixpath.relpath(canonical, alias.parent)
        if expected.endswith("/index.html"):
            expected = expected.removesuffix("index.html")
        if not alias.is_file():
            errors.append(f"Missing alias redirect {alias}")
            continue
        text = alias.read_text()
        if (
            Document(text).hrefs != [expected]
            or "window.location.search" not in text
            or "window.location.hash" not in text
        ):
            errors.append(f"Incorrect alias redirect {alias}")
    return errors


def local_target(directory: Path, source: Path, href: str) -> Path:
    """Resolve local directory URLs to their index without changing the HTML."""
    local_path = unquote(urlsplit(href).path)
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
        target = (source.parent / local_path).resolve() if local_path else source
    return (target / "index.html").resolve() if target.is_dir() else target


def check(directory: Path) -> list[str]:
    errors = []
    versions_file = directory / "versions.json"
    if versions_file.exists():
        versions = json.loads(versions_file.read_text())
        tags = release_tags()
        expected_versions = [
            {"version": "next", "title": "next (draft)", "aliases": []}
        ]
        expected_versions += [
            {"version": tag, "title": tag, "aliases": ["latest"] if i == 0 else []}
            for i, tag in enumerate(tags)
        ]
        if versions != expected_versions:
            errors.append(
                "versions.json must match stable Git tags, newest first, with next first and one latest alias"
            )
        latest = tags[0] if tags else None
        if not (directory / "index.html").is_file():
            errors.append("Missing root redirect")
        elif latest and Document((directory / "index.html").read_text()).hrefs != [
            f"{latest}/"
        ]:
            errors.append("Root redirect does not point to latest")
        if not (directory / "404.html").is_file():
            errors.append("Missing root Pages 404.html")
        elif latest and not {f"/{latest}/", "/next/"}.issubset(
            Document((directory / "404.html").read_text()).hrefs
        ):
            errors.append("Root 404 must link to latest and next")
        if latest:
            errors.extend(alias_errors(directory, latest))
        roots = [directory / v["version"] for v in versions]
    elif (directory / "build-info.json").is_file():
        roots = [directory]
    else:
        roots = [
            p.parent
            for p in directory.glob("*/build-info.json")
            if not json.loads(p.read_text()).get("alias")
        ]
    if not roots:
        return errors + [f"No built versions in {directory}"]
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
        expected_title, latest = expected_draft_title(info["ref"])
        for path in root.rglob("*.html"):
            document = documents[path.resolve()]
            notices = [
                value
                for value in document.banners
                if value.startswith(("Draft of v", "Unreleased changes after v"))
            ]
            if label == "next" and notices != [expected_title]:
                errors.append(
                    f"{path}: missing or incorrect draft banner; expected {expected_title}"
                )
            if label != "next" and notices:
                errors.append(f"{path}: released page has a draft banner")
            if label == "next":
                text = path.read_text()
                if "This text is not released." not in text or "/None/" in text:
                    errors.append(f"{path}: incorrect draft notice")
                if (
                    latest
                    and f"https://spec.portolan-sdi.org/{latest}/" not in document.hrefs
                ):
                    errors.append(f"{path}: draft notice must link to {latest}")
        locations = json.loads((root / "requirements.json").read_text())
        manifest = yaml.safe_load(
            git("show", f"{info['ref']}:specs/portolan/requirements.yaml")
        )
        identifiers = [entry["id"] for entry in manifest["requirements"]]
        expected = set(identifiers)
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
                errors.extend(pdf_errors(path, identifiers))
            else:
                try:
                    errors.extend(epub_errors(path))
                except (zipfile.BadZipFile, KeyError) as error:
                    errors.append(f"{path}: {error}")
        css = root / "assets/stylesheets/extra.css"
        if not css.is_file():
            errors.append(f"{label}: missing extra.css")
        else:
            text = css.read_text()
            if colors := literal_colors(text):
                errors.append(f"{label}: extra.css has literal colors: {colors}")
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
            styles = documents[path.resolve()].styles
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
        targets = [(href, False) for href in document.hrefs] + [
            (src, True) for src in document.images
        ]
        for href, is_image in targets:
            parts = urlsplit(href)
            if parts.scheme or parts.netloc:
                if problem := github_error(href):
                    errors.append(f"{path}: {problem}")
                if is_image and parts.netloc == "github.com" and "/blob/" in parts.path:
                    errors.append(f"{path}: image must use a raw URL: {href}")
                continue
            if is_image and not href:
                errors.append(f"{path}: image has no src")
                continue
            if "stac/json-schema/" in unquote(parts.path):
                errors.append(f"{path}: relative schema link {href}")
            if (
                parts.fragment
                and parts.path
                and posixpath.basename(parts.path) == "index.html"
            ):
                errors.append(
                    f"{path}: non-canonical page URL {href}; use a directory URL"
                )
            target = local_target(directory, path, href)
            if not target.is_relative_to(boundary):
                errors.append(f"{path}: href or src leaves the site: {href}")
                continue
            if not target.is_file():
                errors.append(f"{path}: missing local href or src {href}")
            elif (
                parts.fragment
                and target in documents
                and unquote(parts.fragment) not in documents[target].ids
            ):
                errors.append(f"{path}: missing local anchor {href}")
    return errors


def main() -> int:
    if len(sys.argv) != 2:
        print(
            "Usage: uv run --locked --script site/tests/check_site.py <dir>",
            file=sys.stderr,
        )
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
        "OK: requirements, versions, aliases, downloads, banners, Git links, images, and brand styles"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
