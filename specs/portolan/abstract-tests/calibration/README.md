# Calibration of the pruning-efficiency thresholds

The current pass bar comes from the registry survey on 2026-11-10 and the
sort control below. It replaces the 0.70 bar from the earlier extent-window
draft with 0.65. The row-check calibration on 2026-11-13 supports the two
verdict paths.

The [spatial-order rule](../../formats.md) uses pruning efficiency to compare
how much data a reader can skip with a reference grid.
A row group is a set of rows that Parquet stores together.
The reference grid divides the file's extent into cells for comparison.
The rule applies these thresholds:

| Path | Threshold |
| --- | --- |
| Footer check | Efficiency of at least 0.65 on the row-group boxes, for eight or more row groups |
| Row check | Efficiency of at least 0.65 on ten chunks of rows, for fewer than eight row groups |
| Row floor | No verdict below 200 rows |

The survey below predates the two paths. Its `too-small` verdict and the
clear-failure band no longer exist.

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

## Row-check calibration on 2026-11-13

The registry survey read only footers, so it did not measure the row check.
This calibration sampled at most six files per catalog from each survey
group. It read every row's bbox. It scored the row check on the published
order, a Hilbert-sorted order and a shuffled order of the same rows. It also
repacked the rows into equal row groups and scored the footer check on them.
The data and scripts are in
[the row-check gist](https://gist.github.com/cayetanobv/6e51f10bfbe313fa1f1bcfe31026c36c).

The calibration scored 654 files from 70 catalogs.

| Row check | Minimum | Percentile 5 | Median | Percentile 95 | Maximum |
| --- | ---: | ---: | ---: | ---: | ---: |
| Hilbert-sorted | 0.101 | 0.760 | 0.897 | 0.934 | 0.977 |
| Shuffled | 0.000 | 0.000 | 0.005 | 0.119 | 0.518 |

The highest shuffled score was 0.518, under the 0.65 bar.
Of the sorted files, 6 scored under the bar.
One of them stores 97% of its rows at (0, 0).
The others hold large features and scored 0.57 to 0.64.
No sort can raise these scores. A lower bar would come close to the highest
shuffled score.

On the same published rows, the footer check at eight row groups and the
row check agreed on 648 files. Sorted rows failed the footer check in this
share of files:

| Row groups | Sorted rows that fail the footer check |
| ---: | ---: |
| 2 | 70% |
| 4 | 13% |
| 8 | 2% |
| 16 | 0.2% |

These results set the footer floor at eight row groups. The row check
covers the files below it.

| Survey group | Fail the row check as published | Fixed by a sort |
| --- | ---: | ---: |
| Under 5 MB, never judged before | 13 of 319 | 9 |
| Sent to the row check | 5 of 253 | 5 |

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
