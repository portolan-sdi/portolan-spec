# /// script
# requires-python = ">=3.12"
# dependencies = ["zensical==0.1.1", "pymdown-extensions==13.1", "pyyaml==6.0.3"]
# ///
"""Build archived versions of the specification and its PDF and EPUB editions."""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import markdown
import yaml

SITE = Path(__file__).resolve().parent
ROOT = SITE.parent
SITE_URL = "https://spec.portolan-sdi.org"
PINS = {"pandoc": "3.14", "typst": "0.15.1"}
FONTS_SHA = "fb2d675eec61b618208fed311b7bf951de03a206"
FONT_HASHES = {
    "hanken-grotesk-400.ttf": "5f85843c961d2d954442918d2875ba9106230e1123522156d509a51141bf0e8d",
    "hanken-grotesk-600.ttf": "e09da7b95a89ef949972c73e6c4a174d340a2393e9ec014e5cb778a294d80b5e",
    "hanken-grotesk-700.ttf": "ead263260be11077550fb2b37001d7371b4f9b9e5b065f1379e6985f2c86af4b",
    "jetbrains-mono-400.ttf": "2c57a4ef1168f0b2f91d7e0914b15daf8cf91dbd5b6ebe6c75f3202907cbe964",
    # The pinned brand kit contains 600 as its heaviest Mono TTF.
    "jetbrains-mono-600.ttf": "0ad5c0465821039d9d65ea94a3cedf4d8ece6dd6c7f172abd900d3f272fdcf93",
}
MD_EXTENSIONS = [
    "admonition",
    "attr_list",
    "md_in_html",
    "pymdownx.superfences",
    "pymdownx.tabbed",
    "pymdownx.highlight",
    "tables",
    "toc",
]
# Protect code before matching links, including inline code in a link label.
CODE_SPAN = re.compile(r"(`+)(?!`)([\s\S]*?)(?<!`)\1(?!`)")
INLINE_LINK = re.compile(
    r"(!?\[(?:[^\[\]]|\[[^\]]*\])*\]\(\s*)(<[^>]*>|(?:[^\s()]+|\([^()]*\))+)"
)
REFERENCE = re.compile(r"(^ {0,3}\[[^\]\n]+\]:[ \t]*)(<[^>]*>|\S+)", re.MULTILINE)
FENCE = re.compile(r"^( {0,3})(`{3,}|~{3,})([^\r\n]*)$")
HTML_TAG = re.compile(r"<[A-Za-z][^>]*>")
HTML_URL = re.compile(
    r"((?<![\w:-])(href|src)\s*=\s*)([\"'])(.*?)\3|(?P<bare>(?<![\w:-])(?P<attr>href|src)\s*=\s*)(?P<url>[^\s>]+)",
    re.IGNORECASE,
)
GOOGLE_FONTS_SHA = "c1eda9233c33ad7775b27efd794f931095cf6133"
ITALIC_FONT = "hanken-grotesk-italic.ttf"
ITALIC_HASH = "ae5731726ff75301a3cb63f2e98d1babc77d55ab09fb8e229ca75f5bd46fbe32"
ITALIC_LICENSE_HASH = "e02ccb89a86839b22feff7872ff5cc355cc0f58318d29eee20e2cf83a612f16d"


def git(*args: str) -> str:
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def toolchain() -> None:
    for binary, expected in PINS.items():
        if not shutil.which(binary):
            raise ValueError(
                f"Missing {binary} {expected}. Run site/install-toolchain.sh "
                "site/.toolchain and add site/.toolchain/bin to PATH."
            )
        actual = subprocess.check_output([binary, "--version"], text=True).splitlines()[
            0
        ]
        if actual.split()[1] != expected:
            raise ValueError(
                f"Expected {binary} {expected}; found {actual}. "
                "Use site/install-toolchain.sh to install the pinned toolchain."
            )


def checked_download(path: Path, url: str, expected: str) -> None:
    if not path.exists():
        with urllib.request.urlopen(url, timeout=60) as response:
            data = response.read()
        if hashlib.sha256(data).hexdigest() != expected:
            raise ValueError(f"Font checksum mismatch: {url}")
        path.write_bytes(data)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"Font checksum mismatch: {path}")


def fonts(destination: Path) -> Path:
    configured = os.environ.get("PORTOLAN_FONTS_DIR")
    cache = (
        Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
        / "portolan-spec"
        / "fonts"
    )
    brand = Path(configured) if configured else cache / FONTS_SHA
    if not configured:
        brand.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    for name, expected in FONT_HASHES.items():
        path = brand / name
        if not configured:
            checked_download(
                path,
                f"https://raw.githubusercontent.com/portolan-sdi/portolan-ops/{FONTS_SHA}/brand/fonts/{name}",
                expected,
            )
        if not path.is_file():
            raise ValueError(f"Missing brand font: {path}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Font checksum mismatch: {path}")
        shutil.copyfile(path, destination / name)
    supplemental = cache / GOOGLE_FONTS_SHA
    supplemental.mkdir(parents=True, exist_ok=True)
    base = f"https://raw.githubusercontent.com/google/fonts/{GOOGLE_FONTS_SHA}/ofl/hankengrotesk/"
    for name, remote, checksum in [
        (ITALIC_FONT, "HankenGrotesk-Italic%5Bwght%5D.ttf", ITALIC_HASH),
        ("OFL-hanken-grotesk-italic.txt", "OFL.txt", ITALIC_LICENSE_HASH),
    ]:
        checked_download(supplemental / name, base + remote, checksum)
        shutil.copyfile(supplemental / name, destination / name)
    return destination


def fenced_parts(text: str):
    """Protect CommonMark fences and four-space or tab-indented code blocks."""
    lines = text.splitlines(keepends=True)
    prose = []
    index = 0
    previous_blank = True
    while index < len(lines):
        line = lines[index]
        match = FENCE.match(line.rstrip("\r\n"))
        opens = match and (match[2][0] != "`" or "`" not in match[3])
        indented = (
            (line.startswith("    ") or line.startswith("\t"))
            and line.strip()
            and previous_blank
        )
        if not opens and not indented:
            prose.append(line)
            previous_blank = not line.strip()
            index += 1
            continue
        if prose:
            yield False, "".join(prose)
            prose = []
        code = [line]
        index += 1
        if opens:
            marker = match[2]
            while index < len(lines):
                line = lines[index]
                code.append(line)
                index += 1
                closing = FENCE.match(line.rstrip("\r\n"))
                if (
                    closing
                    and closing[2][0] == marker[0]
                    and len(closing[2]) >= len(marker)
                    and not closing[3].strip()
                ):
                    break
        else:
            while index < len(lines) and (
                not lines[index].strip() or lines[index].startswith(("    ", "\t"))
            ):
                code.append(lines[index])
                index += 1
        yield True, "".join(code)
        previous_blank = not code[-1].strip()
    if prose:
        yield False, "".join(prose)


def normalize_fences(text: str) -> str:
    blocks = []
    for code, block in fenced_parts(text):
        lines = block.splitlines(keepends=True)
        match = FENCE.match(lines[0].rstrip("\r\n")) if code else None
        if match:
            info = match[3].strip().split()
            language = info[0] if info else ""
            lines[0] = f"{match[1]}{match[2]}{language}\n"
            block = "".join(lines)
        blocks.append(block)
    return "".join(blocks)


def rewrite_links(text: str, resolve) -> str:
    prose = "".join(block for code, block in fenced_parts(text) if not code)
    image_labels = {
        " ".join(m[1].lower().split())
        for m in re.finditer(r"!\[[^\]]*\]\[([^\]]+)\]", CODE_SPAN.sub("", prose))
    }

    def rewrite(block: str) -> str:
        protected = []

        def protect(match):
            protected.append(match[0])
            return f"\x02{len(protected) - 1}\x03"

        block = CODE_SPAN.sub(protect, block)

        def replace(match):
            value = match[2]
            angled = value.startswith("<")
            target = value[1:-1] if angled else value
            image = match[1].startswith("!")
            if match.re is REFERENCE:
                label = re.search(r"\[([^\]]+)\]", match[1])[1]
                image = " ".join(label.lower().split()) in image_labels
            result = resolve(target, image=image)
            return match[1] + (f"<{result}>" if angled else result)

        def raw_tag(match):
            def attribute(attr):
                prefix = attr[1] or attr["bare"]
                name = attr[2] or attr["attr"]
                target = attr[4] if attr[1] else attr["url"]
                value = resolve(
                    html.unescape(target), image=name.lower() == "src", html_link=True
                )
                delimiter = attr[3] if attr[1] else '"'
                return prefix + delimiter + html.escape(value, quote=True) + delimiter

            return HTML_URL.sub(attribute, match[0])

        block = INLINE_LINK.sub(replace, block)
        block = REFERENCE.sub(replace, block)
        block = HTML_TAG.sub(raw_tag, block)
        return re.sub(r"\x02(\d+)\x03", lambda m: protected[int(m[1])], block)

    return "".join(
        block if code else rewrite(block) for code, block in fenced_parts(text)
    )


def staged_files(tree: Path) -> dict[str, str]:
    sources = [
        tree / "README.md",
        tree / "stac/README.md",
        tree / "examples/README.md",
        tree / "CHANGELOG.md",
        tree / "stac/CHANGELOG.md",
    ]
    sources += sorted((tree / "specs").rglob("*.md"))
    mapping = {}
    for path in sources:
        rel = path.relative_to(tree)
        if (
            not path.is_file()
            or "node_modules" in rel.parts
            or rel.parts[:2] == ("examples", "catalog")
        ):
            continue
        if rel.name in {"AGENTS.md", "CLAUDE.md"}:
            continue
        target = rel.with_name("index.md") if rel.name == "README.md" else rel
        mapping[rel.as_posix()] = target.as_posix()
    return mapping


def resolve_link(
    target: str,
    source: str,
    mapping: dict[str, str],
    tree: Path,
    revision: str,
    tag: bool,
    image: bool = False,
    html_link: bool = False,
) -> str:
    parts = urlsplit(target)
    if image and parts.netloc == "github.com" and "/blob/" in parts.path:
        return urlunsplit(
            (
                "https",
                "raw.githubusercontent.com",
                parts.path.replace("/blob/", "/", 1),
                parts.query,
                parts.fragment,
            )
        )
    if parts.scheme or parts.netloc or not parts.path:
        return target
    path = posixpath.normpath(
        posixpath.join(posixpath.dirname(source), unquote(parts.path))
    )
    if parts.path.startswith("/"):
        path = posixpath.normpath(unquote(parts.path).lstrip("/"))
    if path == ".." or path.startswith("../"):
        raise ValueError(f"{source}: link climbs above repository root: {target}")
    staged = mapping.get(path) or mapping.get(path.rstrip("/") + "/README.md")
    if staged:
        relative = posixpath.relpath(staged, posixpath.dirname(mapping[source]) or ".")
        if html_link:
            relative = (
                posixpath.relpath(
                    page_url(staged) or ".", page_url(mapping[source]) or "."
                )
                + "/"
            )
        return urlunsplit(("", "", relative, parts.query, parts.fragment))
    versioned = re.fullmatch(r"stac/json-schema/(v\d+\.\d+\.\d+)/schema\.json", path)
    if tag and (
        versioned or path == "stac/json-schema/schema.json" and (tree / path).is_file()
    ):
        version = versioned[1] if versioned else revision
        return urlunsplit(
            (
                "https",
                "schemas.portolan-sdi.org",
                f"/portolan/{version}/schema.json",
                parts.query,
                parts.fragment,
            )
        )
    if image:
        return urlunsplit(
            (
                "https",
                "raw.githubusercontent.com",
                f"/portolan-sdi/portolan-spec/{revision}/{quote(path, safe='/')}",
                parts.query,
                parts.fragment,
            )
        )
    kind = "tree" if (tree / path).is_dir() else "blob"
    return urlunsplit(
        (
            "https",
            "github.com",
            f"/portolan-sdi/portolan-spec/{kind}/{revision}/{quote(path, safe='/')}",
            parts.query,
            parts.fragment,
        )
    )


def toc(text: str) -> list[dict]:
    renderer = markdown.Markdown(
        extensions=MD_EXTENSIONS,
        extension_configs={"pymdownx.tabbed": {"alternate_style": True}},
    )
    renderer.convert(text)

    def flatten(tokens):
        for token in tokens:
            yield token
            yield from flatten(token["children"])

    return list(flatten(renderer.toc_tokens))


def quote_section(text: str, quotation: str) -> str:
    """Match the checker’s whitespace normalization, then find the prior heading."""

    def normalize(value):
        return " ".join(value.split())

    offset = normalize(text).find(normalize(quotation))
    if offset < 0:
        raise ValueError(f"Requirement quote not found: {quotation}")
    headings = []
    consumed = ""
    for code, block in fenced_parts(text):
        if not code:
            for line in block.splitlines(keepends=True):
                if re.match(r"^ {0,3}#{1,6}\s+", line):
                    headings.append(len(normalize(consumed)))
                consumed += line
        else:
            consumed += block
    tokens = toc(text)
    if len(tokens) != len(headings):
        raise ValueError("Source headings do not match the Markdown TOC")
    candidates = [i for i, position in enumerate(headings) if position <= offset]
    if not candidates:
        raise ValueError(f"Requirement quote has no section: {quotation}")
    return tokens[candidates[-1]]["id"]


def requirements_page(
    tree: Path, mapping: dict[str, str], revision: str, tag: bool
) -> tuple[str, list[dict]]:
    entries = yaml.safe_load((tree / "specs/portolan/requirements.yaml").read_text())[
        "requirements"
    ]
    pages = ["# Requirements\n"]
    locations = []
    for entry in entries:
        source = entry["file"]
        anchor = quote_section((tree / source).read_text(), entry["quote"])
        target = f"{mapping[source]}#{anchor}"

        def resolve_quote(value, **options):
            resolved = resolve_link(
                value, source, mapping, tree, revision, tag, **options
            )
            parts = urlsplit(resolved)
            if parts.scheme or parts.netloc:
                return resolved
            path = (
                posixpath.normpath(
                    posixpath.join(posixpath.dirname(mapping[source]), parts.path)
                )
                if parts.path
                else mapping[source]
            )
            return urlunsplit(("", "", path, parts.query, parts.fragment))

        heading = next(
            token["name"]
            for token in toc((tree / source).read_text())
            if token["id"] == anchor
        )
        heading = html.unescape(re.sub(r"<[^>]*>", "", heading))
        quotation = rewrite_links(entry["quote"], resolve_quote)
        pages.append(
            f"## {entry['id']} {{#{entry['id'].lower()}}}\n\n"
            f"Severity: **{entry['severity']}** · Enforcement: **{entry['enforcement']}** · Section: [{heading}]({target})\n\n"
            + "\n".join("> " + line for line in quotation.splitlines())
            + "\n"
        )
        locations.append({"id": entry["id"], "page": mapping[source], "anchor": anchor})
    return "\n".join(pages), locations


def draft_title(version: str, latest: str | None) -> str:
    package_key = semver_key("v" + version)
    if package_key is None:
        raise ValueError(f"Invalid source package version: {version}")
    latest_key = (*map(int, latest[1:].split(".")), (1,)) if latest else None
    if latest_key is not None and package_key <= latest_key:
        return f"Unreleased changes after {latest}"
    return f"Draft of v{version}"


def draft_banner(version: str, latest: str | None) -> str:
    release = f" Read [the newest release]({SITE_URL}/{latest}/)." if latest else ""
    return f'!!! warning "{draft_title(version, latest)}"\n\n    This text is not released.{release}\n\n'


def page_url(path: str) -> str:
    if path == "index.md":
        return ""
    if path.endswith("/index.md"):
        return path[:-8]
    return path[:-3] + "/"


def html_path(directory: Path, page: str) -> Path:
    return directory / page_url(page) / "index.html"


def navigation(mapping: dict[str, str], label: str) -> list:
    nav = [
        {"Home": "index.md"},
        {"Core": "specs/portolan/core.md"},
        {"Formats": "specs/portolan/formats.md"},
        {"Requirements": "requirements.md"},
    ]
    for title, prefix in [
        ("Best practices", "specs/best-practices/"),
        ("Incubating", "specs/incubating/"),
    ]:
        pages = sorted(p for p in mapping.values() if p.startswith(prefix))
        pages.sort(key=lambda p: not p.endswith("/index.md"))
        nav.append(
            {
                title: [
                    {
                        Path(p).stem.replace("-", " ").capitalize()
                        if not p.endswith("/index.md")
                        else "Overview": p
                    }
                    for p in pages
                ]
            }
        )
    nav.extend(
        [
            {"STAC profile": "stac/index.md"},
            {"Examples": "examples/index.md"},
            {"Changelog": "CHANGELOG.md"},
            {"STAC changelog": "stac/CHANGELOG.md"},
            {"PDF": f"downloads/portolan-spec-{label}.pdf"},
            {"EPUB": f"downloads/portolan-spec-{label}.epub"},
        ]
    )
    return nav


def walk_ast(value, visit):
    if isinstance(value, dict):
        visit(value)
        for child in value.values():
            walk_ast(child, visit)
    elif isinstance(value, list):
        for child in value:
            walk_ast(child, visit)


def book(
    docs: Path, output: Path, label: str, date: str, epoch: str, font_dir: Path
) -> None:
    order = [
        "specs/portolan/core.md",
        "specs/portolan/formats.md",
        "requirements.md",
        "specs/best-practices/index.md",
    ]
    order += sorted(
        p.relative_to(docs).as_posix()
        for p in (docs / "specs/best-practices").glob("*.md")
        if p.name != "index.md"
    )
    documents, anchors = {}, {}
    for page in order:
        text = (docs / page).read_text()
        # Markdown admonitions belong to the website; give books a plain draft notice.
        text = re.sub(
            r'^!!! warning "[^\n]+"\n\n    (.*)\n\n',
            r"**Draft.** \1\n\n",
            text,
        )
        document = json.loads(
            subprocess.check_output(
                ["pandoc", "--from=markdown+fenced_divs", "--to=json"],
                input=text,
                text=True,
            )
        )
        headings = []
        walk_ast(
            document["blocks"],
            lambda node: headings.append(node) if node.get("t") == "Header" else None,
        )
        site_headings = toc(text)
        if len(headings) != len(site_headings):
            raise ValueError(f"Book headings differ from site: {page}")
        prefix = page.removesuffix(".md").replace("/", "-")
        for heading, site_heading in zip(headings, site_headings):
            original = site_heading["id"]
            identifier = f"{prefix}--{original}"
            heading["c"][1][0] = identifier
            anchors[page, original] = identifier
        anchors[page, ""] = headings[0]["c"][1][0]
        documents[page] = document

    combined = []
    for page, document in documents.items():

        def fix(node):
            if node.get("t") not in {"Link", "Image"}:
                return
            value = node["c"][-1][0]
            parts = urlsplit(value)
            if parts.scheme or parts.netloc:
                return
            target = (
                posixpath.normpath(
                    posixpath.join(posixpath.dirname(page), unquote(parts.path))
                )
                if parts.path
                else page
            )
            if (target, parts.fragment) in anchors:
                node["c"][-1][0] = "#" + anchors[target, parts.fragment]
            elif target in documents:
                raise ValueError(f"Missing book anchor: {page}: {value}")
            else:
                node["c"][-1][0] = f"{SITE_URL}/{label}/{page_url(target)}" + (
                    f"#{parts.fragment}" if parts.fragment else ""
                )

        walk_ast(document["blocks"], fix)
        combined.extend(document["blocks"])
    merged = next(iter(documents.values()))
    merged["blocks"] = combined
    merged["meta"] = {}
    payload = json.dumps(merged)
    common = [
        "pandoc",
        "--from=json",
        "--standalone",
        "--toc",
        "--metadata=title:Portolan Specification",
        f"--metadata=subtitle:{label}",
        f"--metadata=version:{label}",
        f"--metadata=date:{date}",
        "--metadata=lang:en",
        "--variable=mainfont:Hanken Grotesk",
        "--variable=codefont:JetBrains Mono",
        "--variable=page-numbering:1",
        f"--resource-path={docs}",
    ]
    env = {
        **os.environ,
        "SOURCE_DATE_EPOCH": epoch,
        "TYPST_FONT_PATHS": str(font_dir),
        "TYPST_IGNORE_SYSTEM_FONTS": "true",
    }
    subprocess.run(
        [
            *common,
            "--pdf-engine=typst",
            f"--template={SITE / 'pandoc/spec.typ'}",
            f"--output={output / f'portolan-spec-{label}.pdf'}",
        ],
        input=payload,
        text=True,
        check=True,
        env=env,
    )
    subprocess.run(
        [
            *common,
            "--to=epub3",
            f"--css={SITE / 'pandoc/epub.css'}",
            *[
                f"--epub-embed-font={font_dir / name}"
                for name in [*FONT_HASHES, ITALIC_FONT]
            ],
            f"--output={output / f'portolan-spec-{label}.epub'}",
        ],
        input=payload,
        text=True,
        check=True,
        env=env,
    )


def semver_key(tag: str) -> tuple | None:
    match = re.fullmatch(
        r"v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)"
        r"(?:-([0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*))?"
        r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?",
        tag,
    )
    if not match:
        return None
    prerelease = match[4]
    if prerelease and any(
        part.isdigit() and len(part) > 1 and part.startswith("0")
        for part in prerelease.split(".")
    ):
        return None
    suffix = (
        (1,)
        if prerelease is None
        else (
            0,
            tuple(
                (0, int(part)) if part.isdigit() else (1, part)
                for part in prerelease.split(".")
            ),
        )
    )
    return (*map(int, match.group(1, 2, 3)), suffix)


def releases() -> list[str]:
    tags = []
    for tag in git("tag", "--list", "v*").splitlines():
        if not re.fullmatch(r"v\d+\.\d+\.\d+", tag):
            print(f"Skip tag {tag}: expected vX.Y.Z", flush=True)
        elif tuple(map(int, tag[1:].split("."))) >= (0, 2, 0):
            tags.append(tag)
    return sorted(tags, key=lambda tag: tuple(map(int, tag[1:].split("."))))


def main_ref() -> str:
    refs = [
        ref
        for ref in ("main", "origin/main")
        if subprocess.run(
            ["git", "-C", str(ROOT), "rev-parse", "--verify", f"{ref}^{{commit}}"],
            capture_output=True,
        ).returncode
        == 0
    ]
    if not refs:
        raise ValueError("Neither main nor origin/main exists")
    if len(refs) == 1:
        return refs[0]

    def ancestor(first, second):
        result = subprocess.run(
            ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", first, second]
        )
        if result.returncode not in (0, 1):
            raise ValueError(f"Cannot compare {first} and {second}")
        return result.returncode == 0

    if ancestor("main", "origin/main"):
        return "origin/main"
    if ancestor("origin/main", "main"):
        return "main"
    raise ValueError("main and origin/main diverge; cannot choose next")


def output_root(out: Path) -> Path:
    out = out.expanduser().resolve()
    # CI's fixed contract writes only this artifact directory in the checkout.
    if out == ROOT or out.is_relative_to(ROOT) and out != ROOT / "_site":
        raise ValueError(
            f"Refuse --out inside the source tree: {out}. Use an external directory or the CI artifact path _site."
        )
    return out


def require_build_marker(destination: Path) -> None:
    if destination.is_symlink():
        raise ValueError(f"Refuse output symlink: {destination}")
    if destination.exists() and (
        not destination.is_dir() or not (destination / "build-info.json").is_file()
    ):
        raise ValueError(
            f"Refuse to replace {destination}: missing build-info.json build marker"
        )


def redirect_html(href: str) -> str:
    # mike 2.2.0 templates/redirect.html preserves both query and fragment.
    escaped = html.escape(href, quote=True)
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Redirecting</title>'
        f'<noscript><meta http-equiv="refresh" content="1; url={escaped}"></noscript>'
        f"<script>window.location.replace({json.dumps(href)} + window.location.search + window.location.hash);</script>"
        f'</head><body>Redirecting to <a href="{escaped}">{escaped}</a>.</body></html>\n'
    )


def alias_redirects(out: Path, latest: str) -> None:
    alias = out / "latest"
    require_build_marker(alias)
    if alias.exists():
        shutil.rmtree(alias)
    alias.mkdir()
    (alias / "build-info.json").write_text(
        json.dumps({"alias": "latest", "target": latest}) + "\n"
    )
    for canonical in (out / latest).rglob("*.html"):
        path = alias / canonical.relative_to(out / latest)
        path.parent.mkdir(parents=True, exist_ok=True)
        href = os.path.relpath(canonical, path.parent).replace(os.sep, "/")
        if href.endswith("/index.html"):
            href = href.removesuffix("index.html")
        path.write_text(redirect_html(href))


def build(ref: str, label: str, out: Path, latest: str | None, font_dir: Path) -> None:
    sha = git("rev-parse", "--verify", f"{ref}^{{commit}}")
    full_ref = git("rev-parse", "--symbolic-full-name", ref)
    is_tag = full_ref.startswith("refs/tags/")
    revision = full_ref.removeprefix("refs/tags/") if is_tag else sha
    date = git("show", "-s", "--format=%cs", sha)
    epoch = git("show", "-s", "--format=%ct", sha)
    destination = out / label
    require_build_marker(destination)
    print(f"Build {label} from {revision}", flush=True)
    with tempfile.TemporaryDirectory(prefix="portolan-spec-") as tmp:
        workspace = Path(tmp)
        tree, docs = workspace / "tree", workspace / "docs"
        tree.mkdir()
        docs.mkdir()
        with subprocess.Popen(
            ["git", "-C", str(ROOT), "archive", sha], stdout=subprocess.PIPE
        ) as archive:
            subprocess.run(
                ["tar", "-x", "-C", str(tree)], stdin=archive.stdout, check=True
            )
            archive.stdout.close()
            if archive.wait():
                raise ValueError(f"git archive failed: {ref}")
        mapping = staged_files(tree)
        for source, target in mapping.items():
            text = normalize_fences((tree / source).read_text())
            text = rewrite_links(
                text,
                lambda value, **options: resolve_link(
                    value, source, mapping, tree, revision, is_tag, **options
                ),
            )
            path = docs / target
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        requirements, locations = requirements_page(tree, mapping, revision, is_tag)
        (docs / "requirements.md").write_text(requirements)
        package_version = json.loads((tree / "stac/package.json").read_text())[
            "version"
        ]
        with (docs / "index.md").open("a") as home:
            home.write(
                f"\n## Downloads\n\n[PDF](downloads/portolan-spec-{label}.pdf) · "
                f"[EPUB](downloads/portolan-spec-{label}.epub)\n"
            )
        if label == "next":
            for page in docs.rglob("*.md"):
                page.write_text(
                    draft_banner(package_version, latest) + page.read_text()
                )
        shutil.copytree(SITE / "assets", docs / "assets")
        shutil.copytree(SITE / "overrides", workspace / "overrides")
        downloads = docs / "downloads"
        downloads.mkdir()
        book(docs, downloads, label, date, epoch, font_dir)
        # Retain the exact manifest and section map for offline output validation.
        (docs / "requirements.json").write_text(json.dumps(locations, indent=2) + "\n")
        (docs / "build-info.json").write_text(
            json.dumps(
                {
                    "ref": revision,
                    "label": label,
                    "date": date,
                    "version": package_version,
                },
                indent=2,
            )
            + "\n"
        )
        template = (SITE / "mkdocs.yml").read_text()
        config = {
            "site_url": f"{SITE_URL}/{label}/",
            "docs_dir": "docs",
            "site_dir": "html",
            "nav": navigation(mapping, label),
        }
        # Zensical 0.1.1 config.py and zensical_ui/templates/base.html support this provider.
        extra = {"version": {"provider": "mike"}}
        if label == "next":
            extra.update(
                draft_title=draft_title(package_version, latest),
                latest_release=f"{SITE_URL}/{latest}/" if latest else None,
            )
        additions = yaml.safe_dump(extra, sort_keys=False)
        template = template.replace(
            "extra:\n",
            "extra:\n" + "".join("  " + line + "\n" for line in additions.splitlines()),
        )
        template = template.replace("theme:\n", "theme:\n  custom_dir: overrides\n")
        config_path = workspace / "mkdocs.yml"
        config_path.write_text(
            template + "\n" + yaml.safe_dump(config, sort_keys=False)
        )
        subprocess.run(
            [
                "zensical",
                "build",
                "--strict",
                "--clean",
                "--config-file",
                str(config_path),
            ],
            cwd=workspace,
            check=True,
        )
        require_build_marker(destination)
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(workspace / "html", destination)
        for location in locations:
            built = html_path(destination, location["page"]).read_text()
            if f'id="{location["anchor"]}"' not in built:
                raise ValueError(f"Built TOC has no requirement section: {location}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--ref", help="Git ref to export")
    mode.add_argument(
        "--all", action="store_true", help="Build releases from v0.2.0 and next"
    )
    parser.add_argument("--label", help="Output version directory")
    parser.add_argument("--out", type=Path, required=True, help="Output root")
    args = parser.parse_args()
    if args.all and args.label or args.ref and not args.label:
        parser.error("Use --ref with --label, or --all without --label")
    if args.label and (
        not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", args.label)
        or args.label in {".", ".."}
    ):
        parser.error("--label must be a single directory name")
    try:
        toolchain()
        tags = releases()
        latest = tags[-1] if tags else None
        out = output_root(args.out)
        out.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="portolan-fonts-") as font_tmp:
            font_dir = fonts(Path(font_tmp) / "fonts")
            return build_selected(args, out, tags, latest, font_dir)
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        return 1


def build_selected(
    args, out: Path, tags: list[str], latest: str | None, font_dir: Path
) -> int:
    if args.all:
        if not latest:
            raise ValueError("No release tags at or above v0.2.0")
        for tag in tags:
            build(tag, tag, out, latest, font_dir)
        build(main_ref(), "next", out, latest, font_dir)
        versions = [
            {
                "version": tag,
                "title": tag,
                "aliases": ["latest"] if tag == latest else [],
            }
            for tag in reversed(tags)
        ]
        versions.insert(0, {"version": "next", "title": "next (draft)", "aliases": []})
        (out / "versions.json").write_text(json.dumps(versions, indent=2) + "\n")
        alias_redirects(out, latest)
        (out / "index.html").write_text(redirect_html(f"{latest}/"))
        (out / "404.html").write_text(
            '<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Page not found</title></head>'
            f'<body><h1>Page not found</h1><p>Read <a href="/{latest}/">the newest release</a> '
            'or <a href="/next/">the next draft</a>.</p></body></html>\n'
        )
    else:
        build(args.ref, args.label, out, latest, font_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
