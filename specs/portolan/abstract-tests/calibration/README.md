# Calibration corpus for the pruning-efficiency bar

The spatial-ordering rule in [`formats.md`](../../formats.md) passes a file at
efficiency 0.70, judges a pass from eight row groups, fails the clear case
under 0.25, and exempts files under 5 MB. Those numbers came from
measurements, and this directory stores the measurements, so anyone can
check them and argue for different numbers with data.

## The measurements behind the thresholds

The 0.70 bar was set from a survey of 206 files across every catalog in the
[Portolan registry](https://github.com/portolan-sdi/portolan-registry), plus a
review across four further catalogs (Madrid, Extremadura, Andalucía, South
Tyrol), three single files (US Census TIGER, CAL FIRE perimeters, Natural
Earth), and 1.27 million NOAA AIS tracks. In the registry survey one file
scored 0.00, eight fell between 0.53 and 0.70, and the next scored 0.72;
every file in that band reached 0.87 to 0.97 after a spatial sort. The full
review is in
[this gist](https://gist.github.com/cayetanobv/75745d208e5bf0e3431d10daa7c8a8dc).

Those measurements used the earlier draft of the metric, whose query window
was sized by the extent and placed uniformly over it. The current rule places
the window by rows, sizes it by the row group around its centre, and weighs bytes.
The ordering of good and bad files is unchanged on every abstract test vector,
but the bar carries over from the old measurement until this corpus is
re-measured under the current definition. The bar moves only with that
evidence.

## Re-running the measurement

[`measure.py`](measure.py) computes the current metric for every Parquet file
under a directory, from the footers alone, and writes one CSV row per file:

```bash
uv run specs/portolan/abstract-tests/calibration/measure.py <directory> --out results.csv
```

Point it at a checkout of the registry's catalogs (or any corpus of GeoParquet
files). The columns record each file with its row-group count and its
compressed bytes, then the achieved and achievable skip rates, the
efficiency, and the area sum. A
file without per-row-group spatial statistics gets `no-statistics` in the
`note` column.

To propose a different bar or floor, open a pull request that adds your
`results.csv` beside this file, names the corpus it was measured on, and
says which files the new number would re-classify.

## What belongs here

- `measure.py` — the measurement script, a direct transcription of the spec's
  formulas. It must reproduce
  [`../spatial-metric-vectors.json`](../spatial-metric-vectors.json)
  (`--self-test` runs that check).
- `results-*.csv` — measured corpora, one file per corpus, named for the
  corpus and the date, such as `results-registry-2026-11.csv`.
