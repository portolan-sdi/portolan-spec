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

Covers the two rules formats.md raises to MUSTs on top of a valid COG, per OGC
21-026's Optimized GeoTIFF requirements class.

Overviews (`/req/optimized_geotiff/number`), which rashid enforces as PTL-DAT-011.
A raster wider or taller than one 512px tile MUST carry internal overviews,
halving until the coarsest level fits inside a tile. A raster already smaller
than a tile is exempt, since it is its own overview.

Band statistics, which rashid enforces as PTL-DAT-009 and PTL-DAT-010. Every band
carries embedded STATISTICS_* tags, and valid percent is a MUST once the band has
a nodata value.

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
from convert import bands_from_cog, to_cog  # noqa: E402

TILE = 512
STAT_KEYS = ("STATISTICS_MINIMUM", "STATISTICS_MAXIMUM", "STATISTICS_MEAN",
             "STATISTICS_STDDEV", "STATISTICS_VALID_PERCENT")


def _write(path: Path, arr, nodata=None) -> None:
    count, height, width = arr.shape
    with rasterio.open(path, "w", driver="GTiff", height=height, width=width,
                       count=count, dtype=arr.dtype.name, crs="EPSG:4326",
                       nodata=nodata, transform=from_bounds(0, 0, 2, 1, width, height)) as dst:
        dst.write(arr)


def check_small_raster_is_exempt(tmp: Path) -> None:
    """A raster smaller than one tile needs no overviews, and must not be given
    pointless ones."""
    src, out = tmp / "small.tif", tmp / "small-cog.tif"
    _write(src, np.stack([np.full((64, 64), 10, "uint8"), np.full((64, 64), 20, "uint8")]))

    assert to_cog(src, out, None) == "EPSG:4326"
    valid, _, _ = cog_validate(str(out))
    assert valid, "small output is not a valid COG"

    with rasterio.open(out) as ds:
        assert max(ds.width, ds.height) <= TILE, (ds.width, ds.height)
        assert not ds.overviews(1), f"exempt raster was given overviews {ds.overviews(1)}"
        tags = ds.tags(1)
        for key in STAT_KEYS:
            assert key in tags, f"band 1 missing {key}: {tags}"
        assert tags["STATISTICS_MINIMUM"] == "10.0", tags
        assert tags["STATISTICS_MAXIMUM"] == "10.0", tags
        # No nodata, so every pixel is valid.
        assert float(tags["STATISTICS_VALID_PERCENT"]) == 100.0, tags


def check_large_raster_gets_overviews(tmp: Path) -> None:
    """A raster larger than one tile carries overviews down to a single tile,
    each level halving the one above it."""
    src, out = tmp / "large.tif", tmp / "large-cog.tif"
    rng = np.random.default_rng(0)
    _write(src, rng.integers(1, 255, (1, 2100, 1700), dtype="uint8"))

    to_cog(src, out, None)
    valid, _, _ = cog_validate(str(out))
    assert valid, "large output is not a valid COG"

    with rasterio.open(out) as ds:
        overviews = ds.overviews(1)
        assert overviews, "raster larger than one tile carries no overviews"
        assert overviews == [2 ** (i + 1) for i in range(len(overviews))], overviews
        # "until the coarsest level spans one tile across or down", so one
        # dimension inside a tile is the bar. Measure the shorter side.
        coarsest = min(ds.width, ds.height) / overviews[-1]
        assert coarsest <= TILE, f"coarsest overview spans {coarsest}px, over one {TILE}px tile"
        finer = min(ds.width, ds.height) / overviews[-2] if len(overviews) > 1 else None
        assert finer is None or finer > TILE, f"overviews built past one tile: {overviews}"


def check_nodata_band_reports_valid_percent(tmp: Path) -> None:
    """Valid percent is a MUST on a band with a nodata value, and counts only the
    pixels that are not nodata, both in the embedded tag and in the STAC band."""
    src, out = tmp / "nodata.tif", tmp / "nodata-cog.tif"
    arr = np.full((1, 100, 100), 7, "uint8")
    arr[0, :25, :] = 0  # a quarter of the band is nodata
    _write(src, arr, nodata=0)

    to_cog(src, out, None)
    with rasterio.open(out) as ds:
        tags = ds.tags(1)
        assert float(tags["STATISTICS_VALID_PERCENT"]) == 75.0, tags
        assert tags["STATISTICS_MINIMUM"] == "7.0", tags

    stats = bands_from_cog(out)[0]["statistics"]
    assert stats["valid_percent"] == 75.0, stats
    assert stats["minimum"] == 7.0, stats


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d)
        check_small_raster_is_exempt(tmp)
        check_large_raster_gets_overviews(tmp)
        check_nodata_band_reports_valid_percent(tmp)
    print("OK, rio-cogeo COG with size-derived overviews and valid-percent stats")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
