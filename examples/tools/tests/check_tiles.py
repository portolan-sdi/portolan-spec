# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "numpy",
#   "Pillow>=11",
# ]
# ///
"""Standalone check for tiles.fetch_basemap.

Exercises the pure zoom/tile math and mosaics a pre-seeded tile cache with no
network, so the test needs neither GDAL nor internet.
Run: uv run examples/tools/tests/check_tiles.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import tiles  # noqa: E402

_ORIGIN = 20037508.342789244


def check_zoom_matches_resolution() -> None:
    # A framed extent one tenth of the world wide, asked for at 768 px, should
    # pick a zoom whose 256-px tiles roughly cover that width.
    span = (2 * _ORIGIN) / 10
    merc = [-span / 2, -span / 2, span / 2, span / 2]
    z = tiles._tile_zoom(merc, 768)
    assert isinstance(z, int) and 0 <= z <= 19, z
    # world px at z must put ~768 px across a tenth of the world
    px = span / (2 * _ORIGIN) * (256 * 2 ** z)
    assert 384 <= px <= 1536, f"zoom {z} gives {px:.0f}px across, want ~768"


def check_mosaic_from_seeded_cache() -> None:
    merc = [-_ORIGIN / 4, -_ORIGIN / 4, _ORIGIN / 4, _ORIGIN / 4]
    w, h = 200, 200
    with tempfile.TemporaryDirectory() as d:
        cache = Path(d)

        # Pre-seed every tile the fetcher will ask for with a solid red tile,
        # by intercepting _fetch_tile so no HTTP happens.
        def fake_fetch(url: str, z: int, x: int, y: int, cache: Path) -> Path:
            p = cache / "tiles" / str(z) / str(x) / f"{y}.png"
            p.parent.mkdir(parents=True, exist_ok=True)
            if not p.exists():
                Image.new("RGB", (256, 256), (255, 0, 0)).save(p)
            return p

        tiles._fetch_tile = fake_fetch
        arr = tiles.fetch_basemap("http://example/{z}/{x}/{y}.png", merc, w, h, cache)
    assert arr.shape == (h, w, 3), arr.shape
    assert arr.dtype == np.uint8, arr.dtype
    assert (arr[..., 0] == 255).all() and (arr[..., 1] == 0).all(), "mosaic not solid red"


def main() -> int:
    check_zoom_matches_resolution()
    check_mosaic_from_seeded_cache()
    print("OK, tiles zoom + mosaic")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
