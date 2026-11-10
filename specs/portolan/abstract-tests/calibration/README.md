# Calibration of the pruning-efficiency thresholds

The current pass bar comes from the registry survey on 2026-11-10 and the
sort control below. It replaces the 0.70 bar from the earlier extent-window
draft with 0.65.

The [spatial-order rule](../../formats.md) uses pruning efficiency to compare
how much data a reader can skip with a reference grid.
A row group is a set of rows that Parquet stores together.
The reference grid divides the file's extent into cells for comparison.
The rule applies these thresholds:

| Check | Threshold |
| --- | --- |
| Size floor | No order verdict below 5,000,000 compressed bytes (5 MB) |
| Footer pass | Efficiency of at least 0.65 with eight or more row groups |
| Footer clear failure | Efficiency under 0.25 with three to seven row groups |
| Row check | The same 0.65 bar when the footer gives no verdict, for files of at least 5 MB |

## Registry survey on 2026-11-10

The survey read every catalog in the
[Portolan registry](https://github.com/portolan-sdi/portolan-registry).
It followed STAC child and item links and attempted to read at most three
data Parquet files per collection. It read file footers through HTTP range
requests. The command was:

```bash
uv run specs/portolan/abstract-tests/calibration/measure.py --registry <portolan-registry checkout> --per-collection 3
```

The results are in `results-registry-2026-11.csv` in
[the calibration gist](https://gist.github.com/nlebovits/5c123a65d8d448875751f431f9c77475).
The survey recorded 5,914 files from 74 catalogs.
One catalog, `bot-open-data`, served a `catalog.json` that is not valid JSON.

| Result | Files |
| --- | ---: |
| No per-row-group spatial statistics | 2,635 |
| HTTP 404 from links to Overture data that moved | 37 |
| Under the 5 MB size floor | 2,364 |
| Footer pass | 308 |
| Row check with one row group | 309 |
| Row check with two to seven row groups | 261 |
| Footer failure | 0 |

The 2,635 files without spatial statistics have neither a bbox covering nor
native spatial statistics. A bbox covering stores each row's bounding box
in separate fields.
The row check receives 570 files in total.

One catalog, `harmonized-field-data`, supplies 183 of the 878 files that reach
the size floor. This concentration limits how well the survey represents other data sources.

The 308 files with eight or more row groups score about 0.1 lower under the
current metric than under the earlier extent-window draft.
The CSV column `efficiency_extent_window` records the earlier score for each
file.

## Sort control

The control downloaded each eligible file and wrote a Hilbert-sorted copy
with `gpio sort hilbert`. It kept the same rows per row group and measured
the copy with the current metric.
It selected files with a score under 0.85 and a compressed size under
300 MB from those eligible for a footer score.
The command was:

```bash
uv run specs/portolan/abstract-tests/calibration/resort.py results-registry-2026-11.csv --below 0.85 --max-bytes 300000000
```

The results are in `resort-registry-2026-11.csv` in the same gist.
The control selected 145 files and measured 141 copies.
Among the 32 measured copies with eight or more row groups, efficiency
ranged from 0.696 to 0.944. The median was 0.91.
The source files below 0.70 in this group were:

| File | Before sort | After sort | Interpretation |
| --- | ---: | ---: | --- |
| `portolan-nl` crop parcels 2011, `brp_gewaspercelen_2011.parquet` | 0.668 | 0.912 | The sort corrected poor order. |
| `osm-geoparquet-north-america` Manitoba buildings | 0.682 | 0.696 | The file was already sorted. The 0.70 bar rejects it even though another sort cannot fix its score. |

The current 0.65 bar lets every sorted copy with eight or more row groups
pass. It also lets the original 2011 crop-parcel file pass at 0.668.
The row check uses the same bar.

The lowest sorted scores at smaller row-group counts were:

| Row groups | Lowest efficiency |
| ---: | ---: |
| Two | 0.18 |
| Three | 0.34 |
| Four | 0.41 |
| Five | 0.56 |
| Six | 0.68 |
| Seven | 0.75 |

The two-group sample had 47 files and a median efficiency of 0.57.
These scores explain why the footer check allows a pass only from eight
row groups.

The earlier clear-fail rule rejected efficiency under 0.25 from two row
groups. It failed six files, all with two groups.
Two of those files still scored below 0.25 after the sort:

| Before sort | After sort |
| ---: | ---: |
| 0.198 | 0.202 |
| 0.239 | 0.239 |

Another file scored 0.293 before the sort and 0.178 after it.
Each half of a sorted file can span most of its extent.
The current clear-fail rule starts at three row groups to avoid these false
failures. The minimum sorted score at three or more groups was 0.34.

## Earlier survey

The earlier 0.70 bar came from 206 files across every catalog then in the
registry. Cayetano also reviewed four catalogs and three single files:

| Type | Sources |
| --- | --- |
| Catalogs | Madrid, Extremadura, Andalucía, South Tyrol |
| Single files | Census TIGER (United States), CAL FIRE perimeters, Natural Earth |

The review also included 1.27 million NOAA AIS tracks.
In the registry sample, one file scored 0.00 and eight scored between 0.53
and 0.70. The next file scored 0.72.
Every file below the bar reached 0.87 to 0.97 after a spatial sort.
[Cayetano's full review](https://gist.github.com/cayetanobv/75745d208e5bf0e3431d10daa7c8a8dc)
records this work.

Those measurements used the extent-window draft.
It placed query windows uniformly over the extent and sized them to that
extent. The current metric places windows by row count and sizes them to the
selected box. It weights the read cost by bytes.
The abstract test vectors rank good and bad files the same way under both
metrics. The current bar comes from the new survey and sort control.

## Repeat the measurements

[`measure.py`](measure.py) implements the formulas in the spec.
It reads only footers and writes one CSV row per file.
For a local corpus, use:

```bash
uv run specs/portolan/abstract-tests/calibration/measure.py <directory> --out results.csv
```

For a registry checkout, use `--registry` as in the survey command.
The script records the file's row-group count and compressed bytes.
It also records the achieved and achievable skip rates, efficiency, and area
sum. The skip rate is the share of bytes that a query avoids.
The achievable rate is the reference grid's rate.
The area sum divides the sum of box areas by the extent's area.
The script writes `no-statistics` in `note` when a file lacks per-row-group
spatial statistics.

[`resort.py`](resort.py) creates and measures the sorted control copies.
It requires `gpio` on the PATH.
Use `uv tool install geoparquet-io` to install it.
Both scripts accept `--out` to set the output path.
Their default output names are `results.csv` and `resort.csv`.
The survey outputs use the dated names in this README.

To check the formula implementation against
[`../spatial-metric-vectors.json`](../spatial-metric-vectors.json), run:

```bash
uv run specs/portolan/abstract-tests/calibration/measure.py --self-test
```

To propose another bar or floor, open a pull request that changes the
numbers and links your results file. Publish the file outside this
repository, for example as a gist. Name the corpus and the measurement date.
State which files the proposed threshold would reclassify.
