# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "duckdb>=1.5.5",
#   "rasterio>=1.5",
#   "rio-cogeo>=5.3",
#   "numpy",
# ]
# ///
"""Standalone check for convert.to_cog on rio-cogeo.

Builds a tiny 2-band raster, runs to_cog, and asserts the output is a valid COG
with overviews and STATISTICS_* band tags that match the pixel values.
Run: uv run examples/tools/tests/check_cog.py
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rio_cogeo.cogeo import cog_validate

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from convert import to_cog  # noqa: E402


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        src = tmp / "src.tif"
        arr = np.stack([np.full((64, 64), 10, "uint8"), np.full((64, 64), 20, "uint8")])
        transform = from_bounds(0, 0, 2, 1, 64, 64)
        with rasterio.open(src, "w", driver="GTiff", height=64, width=64, count=2,
                           dtype="uint8", crs="EPSG:4326", transform=transform) as dst:
            dst.write(arr)

        out = tmp / "out.tif"
        code = to_cog(src, out, None)
        assert code == "EPSG:4326", code

        valid, _, _ = cog_validate(str(out))
        assert valid, "output is not a valid COG"
        with rasterio.open(out) as ds:
            assert ds.overviews(1), "no overviews on band 1"
            tags = ds.tags(1)
            assert tags.get("STATISTICS_MINIMUM") == "10.0", tags
            assert tags.get("STATISTICS_MAXIMUM") == "10.0", tags
    print("OK, rio-cogeo COG with overviews and stats")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
