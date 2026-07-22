"""Small shared helpers, subprocess runner, checksums, and value formatting."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path
from typing import Any


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


def _sql_lit(v: Any) -> str:
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, (int, float)):
        return str(v)
    return "'" + str(v).replace("'", "''") + "'"


def _hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
