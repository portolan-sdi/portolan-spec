# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pyyaml>=6.0.3",
#   "duckdb>=1.5.5",
#   "jsonschema>=4.26.0",
#   "pyarrow>=25",
#   # Bounded because this writer determines the published file:checksum of
#   # items.parquet and the row-group layout PTL-DAT-006 and PTL-DAT-016 read.
#   # A change to its arrow schema or its to_parquet defaults rewrites those
#   # bytes. 0.8.1 is what resolves today and is the floor.
#   "stac-geoparquet>=0.8.1",
#   "geoparquet-io @ git+https://github.com/yharby/geoparquet-io.git@f27e53108910f19bd74a9ff4be5c7d97b104753c",
#   "rasterio>=1.5",
#   # Pinned to the exact merge commit of portolan-sdi/rashid#87, which answers
#   # the rashid#86 we filed from this work. It adds --data-scope local, so a
#   # metadata-only mirror runs every local data rule without streaming a single
#   # remote byte. No release carries it yet, v0.1.3 predates the merge, so this
#   # is a commit pin rather than main to keep the build reproducible. Return
#   # this to a version range once it ships.
#   "rashid[data] @ git+https://github.com/portolan-sdi/rashid@8d9e11f2b742e2873a2f397a182c8e1aace07dcc",
#   "rio-cogeo>=5.3",
#   "Pillow>=11",
# ]
# ///
"""
Portolan reference catalog generator.

Reads every YAML manifest in a directory and builds each one into its own
complete, v0.1-conformant Portolan STAC catalog. One manifest file describes one
whole catalog and holds everything catalog-specific, so this script carries no
per-catalog values. For each collection it downloads the true original source
once, converts it to a cloud-native canonical asset (GeoParquet for vector and
tabular, COG for raster), builds derivatives (PMTiles, thumbnail, MapLibre
styles), computes real file:size and sha2-256 multihash file:checksum for every
asset, and also cites the original file as a source-role asset. It validates the
output against the committed Portolan schema.

The generator is a small set of plain sibling modules under examples/tools/, run
through this build.py entrypoint. config holds the static constants, common the
shared helpers, fetch the downloader, convert the format conversions,
derivatives the PMTiles and MapLibre styles, thumbnails the previews, stacio the
STAC assembly and catalog builders, and validate the conformance checks.

Prerequisites (FOSS, on PATH): tippecanoe and uv. The data and thumbnail paths
run on DuckDB spatial, rasterio, and rio-cogeo, which vendor their own GDAL
inside their wheels, so no GDAL command-line install is needed.

Run:
    uv run examples/tools/build.py
    uv run examples/tools/build.py --catalog portolan-reference
    uv run examples/tools/build.py --only boundaries/us-counties
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from check_catalogs import load_baseline
from stacio import load_manifest, build_catalog
from validate import validate


# ------------------------------------------------------------------------- main
def _repo_root() -> Path:
    # examples/tools/build.py -> repo root is three levels up
    return Path(__file__).resolve().parent.parent.parent


def main() -> int:
    root = _repo_root()
    ap = argparse.ArgumentParser(description="Generate Portolan catalogs from manifests")
    ap.add_argument("--manifests", default=root / "examples/manifests", type=Path,
                    help="directory of *.yaml catalog manifests")
    ap.add_argument("--out", default=root / "examples/catalog", type=Path,
                    help="output root, each manifest builds into <out>/<stem>")
    ap.add_argument("--cache", default=root / "examples/.cache", type=Path)
    ap.add_argument("--catalog", default=None, help="build only the manifest with this file stem")
    ap.add_argument("--only", default=None, help="build only this collection id")
    ap.add_argument("--schema", default=root / "stac/json-schema/v0.1.0/schema.json", type=Path)
    ap.add_argument("--no-validate", action="store_true")
    args = ap.parse_args()

    files = sorted(p for p in args.manifests.glob("*.yaml"))
    files += sorted(p for p in args.manifests.glob("*.yml"))
    if args.catalog:
        files = [p for p in files if p.stem == args.catalog]
    if not files:
        raise SystemExit(f"no manifests found in {args.manifests}")

    for mf in files:
        print(f"=== manifest {mf.name} ===", file=sys.stderr)
        manifest = load_manifest(mf)
        cat_out = args.out / mf.stem
        build_catalog(manifest, cat_out, args.cache, args.only)
        if not args.no_validate and not args.only:
            baseline = load_baseline(root, cat_out)
            validate(cat_out, args.schema, baseline=baseline or None)
    print("done", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
