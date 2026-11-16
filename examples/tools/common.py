"""Small shared helpers, subprocess runner, checksums, and value formatting."""
from __future__ import annotations

import hashlib
import re
import subprocess
from pathlib import Path
from typing import Any

# A raster-scenes Item id ends in its grid row and column, 1-based.
ITEM_GRID = re.compile(r"-r(\d+)c(\d+)$")


def item_id(stem: str, row: int, column: int) -> str:
    """The id of the scene Item at a 1-based grid row and column."""
    return f"{stem}-r{row}c{column}"


def item_grid(name: str) -> tuple[int, int] | None:
    """The 1-based (row, column) that an Item id or file stem ends in, or None."""
    match = ITEM_GRID.search(name)
    return (int(match.group(1)), int(match.group(2))) if match else None


def run(cmd: list[str], **kw: Any) -> subprocess.CompletedProcess:
    kw.setdefault("check", True)
    kw.setdefault("text", True)
    kw.setdefault("capture_output", True)
    p = subprocess.run(cmd, **kw)
    return p


def filesize(p: Path) -> int:
    return p.stat().st_size


def multihash(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    # sha2-256 multihash: 0x12 function code, 0x20 (32) digest length, then digest
    return (bytes([0x12, 0x20]) + h.digest()).hex()


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
