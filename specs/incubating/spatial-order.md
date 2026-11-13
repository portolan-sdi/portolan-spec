# Spatial order

> **Status: incubating.** This method is not part of conformance for the
> current Portolan version. The normative rule is in
> [`formats.md`](../portolan/formats.md#parquet): rows MUST follow a spatial
> order that places nearby features near each other in the file. This
> document describes how a validator can measure that order and report it.
> Validators report the result as a warning, not as a conformance failure.

The method moves into `formats.md` after the v0.3 release if the pass bar and
the row-group floor hold on real catalogs, and if a second validator
reproduces the [test vectors](spatial-order/spatial-metric-vectors.json).
Discussion happens in
[#188](https://github.com/portolan-sdi/portolan-spec/pull/188).

## Terms

A row group is a set of rows that Parquet stores together.
Its footer statistics let a reader skip the group without reading its data.
A bbox covering stores each row's bounding box in separate fields.

## Method

A validator judges spatial order with pruning efficiency on one of two paths.
A file with eight or more row groups takes the footer check.
The count includes only row groups with a bounding box.
A file with fewer than eight row groups takes the row check.
Both checks use the same metric and the same pass bar.[^paths]
A validator that follows this method gives a verdict on every file that has
enough rows. Other tools can report the statistics without a verdict.

**Pruning efficiency.** Pruning means that a reader skips data it does not
need for a query. The skip rate is the share of the file's bytes that the
reader can skip. Efficiency compares this rate with the rate for a reference
layout over the same extent.

The metric takes a layout of `n` bounding boxes
`B_i = (bx0, by0, bx1, by1)`. Each box has a row count `r_i` and a byte count
`s_i`. For a row group, the footer supplies its row count and total compressed
size. A layout without byte counts uses `s_i = r_i`.
The row check uses this substitution for its chunks.
The extent `E` is the union of the boxes. The metric does not use the bbox
that the file declares.

A query window represents the area that a reader queries.
The metric places this window where the data is and sizes it to the data's
scale.[^placement] It chooses box `B_i` with probability `r_i / N`, where
`N = Σ r_i`. It then places the window's center `c` uniformly within that box.
The window spans 10% of each dimension of `B_i`.
Its width is `w = 0.10 (bx1_i − bx0_i)` and its height is
`h = 0.10 (by1_i − by0_i)`.

To calculate whether the window overlaps `B_j`, expand `B_j` by half the
window's size on each side. The window overlaps `B_j` exactly when `c` falls
inside this expanded box. The following formula calculates that probability
without a random sample.[^expectation]
On one axis, `[a0, a1]` is the span of `B_i` from which the metric draws the
center coordinate. The expanded target span is
`[g0, g1] = [bx0_j − w/2, bx1_j + w/2]`.
The overlap probability on that axis is:

```
F = clip((min(a1, g1) − max(a0, g0)) / (a1 − a0), 0, 1)
```

A span with no width (`a1 = a0`) has only one possible center coordinate.
In that case, `F` is 1 when `g0 <= a0 <= g1` and 0 otherwise.
The probability that a query window overlaps `B_j` combines the factors for
both axes:

```
P_j = Σ_i (r_i / N) · Fx(i, j) · Fy(i, j)
```

The expected skip rate weights each box by its share of the file's bytes.
This measures the data transfer that a reader avoids:

```
skip = 1 − Σ_j (s_j / S) · P_j        where S = Σ s_j
```

The reference grid divides the extent into cells that serve as a comparison
layout. The reference layout MUST use the following near-square grid of `n`
cells with uniform `r_i` and `s_i`.[^grid]
The construction is:

```
cols = ceil(sqrt(n))
rows = ceil(n / cols)
last = n − cols · (rows − 1)
```

Every grid row is `(Y1 − Y0) / rows` tall.
Every row except the last has `cols` cells, each `(X1 − X0) / cols` wide.
The last row has `last` cells, each `(X1 − X0) / last` wide.
Each row spans the full width of the extent.
The grid covers the whole extent with no empty cells.
Efficiency is the layout's skip rate divided by the reference skip rate,
clipped at 1:

```
efficiency = min(1, skip(layout) / skip(reference))
```

A layout passes when its efficiency is 0.65 or more.
The validator gives no verdict when the reference skip rate is 0, because
efficiency is undefined. This occurs for `n = 1` and for an extent that is a
point. At a point, every span has no width and every `F` is 1.
The validator does judge an extent that is zero on only one axis.
The one-coordinate rule gives that axis a factor of 1.
The other axis determines the score.

A validator MUST reproduce the expected values in the abstract test vectors in
[`spatial-order/spatial-metric-vectors.json`](spatial-order/spatial-metric-vectors.json).
These vectors specify the results of the preceding definitions.

Efficiency measures order at the scale of the row groups.
The metric places windows by row count and sizes them to the box around
their center. A few distant features cannot stretch the extent to make a
shuffled file pass or a sorted file fail.
The vectors `outlier-shuffled-n20` and `outlier-sorted-n20` test these cases.
Large features can still make a sorted file fail.
No spatial order can make their bounding boxes small relative to the extent.
The area sum is the sum of the box areas divided by the extent's area,
`Σ area(B_i) / area(E)`. This statistic helps identify files with large
features. A sort can reduce the area sum several times over without changing
the verdict.

**Footer check.** A file with eight or more row groups passes when the
efficiency of its row-group boxes is at or above the pass bar.[^pruning]
The validator reads these boxes from the per-row-group spatial statistics.
A validator MUST NOT judge a file with fewer than eight row groups by its
row-group boxes. It MAY report their statistics.[^floor]
When the efficiency of the row-group boxes is undefined, the validator applies
the row check.

**Row check.** For a file with fewer than eight row groups, or without
per-row-group spatial statistics, the validator computes the same efficiency
on ten chunks of rows in file order:

1. Take the `N` rows in file order. Chunk `k`, for `k` from 0 to 9, holds
   the rows with zero-based index `i` such that
   `floor(k * N / 10) <= i < floor((k + 1) * N / 10)`.
2. Find each row's box. A row's box is its bbox covering when the file has
   one. Otherwise, the box is the minimum and maximum of the row's
   coordinates in the primary geometry column. This rule lets the row check
   judge native files without a covering. For `GEOGRAPHY`, the coordinate
   box is an approximation, because geodesic edges can extend past their
   vertices.
3. A row with a null covering, or a null or empty geometry, has no box. It
   keeps its position in its chunk, but it does not extend the chunk's box.
4. A chunk's box is the union of its rows' boxes. Leave out a chunk with no
   boxed rows. The number of remaining chunks is `n`.
5. Give each chunk a row count `r_i` equal to its boxed rows, and a byte
   count `s_i` equal to that row count. With all ten chunks present, the
   reference grid divides the extent into 4 + 4 + 2 cells.
6. Apply the pass bar of any layout.

The test needs 200 rows with a bounding box, which is ten chunks of twenty
rows. Below that count, a validator MUST report that the file has too few
rows to judge. It MUST NOT withhold that message.

**Reporting.** A validator MUST start its verdict with the expected share of
the file's bytes that the query window reads.
This states the absolute cost, as in "a typical query reads 23% of the file".
With every verdict, a validator MUST also report the efficiency, the
achievable skip rate, and the area sum as statistics that give no separate
verdict.
The achievable skip rate is the reference grid's skip rate.
When the extent has no area, the area sum is undefined.
A validator MUST report an undefined area sum as absent rather than as 0.
On a failure, a validator SHOULD identify the row groups whose boxes are
largest relative to the extent.
This helps a publisher see whether one outlier or the whole file causes the
failure. A validator SHOULD also report the read share for windows at 1% and
at 25% of each dimension beside the 10% figure.

A validator MAY report the fraction of consecutive row-group pairs whose
boxes overlap as a statistic. It MUST NOT base its verdict on that fraction.[^overlap]

## Page-level statistics

A validator MAY use page-level statistics to refine the read share it reports.
These statistics can come from the Parquet page index on the covering leaves
or from page-level native statistics.
The verdict uses the preceding row-group metric.
Validators agree on the verdict whether or not they read the page index.[^pagestats]

[^paths]: The verdict depends on the order of the rows. It does not depend
    on the file size or the compression codec. In the November 2026
    row-check calibration on 654 registry files, shuffled rows never reached
    0.65, and the highest scored 0.52. Hilbert-sorted rows had a median of
    0.90. On the same rows, the footer check at eight row groups and the row
    check agreed on 648 files. The
    [calibration README](spatial-order/calibration/README.md) links the data.

[^placement]: An earlier draft placed the window uniformly over the extent
    and sized it to that extent. One distant row could stretch the
    extent enough to make a shuffled file pass.
    Most windows then fell on empty space.
    The same outlier could make a sorted file fail because the window grew
    as large as the whole data region.
    The current metric avoids both errors with information from the footer.
    It places windows by row count and sizes them to the box around their
    center.

[^expectation]: The skip rate is the expected value of a sampling process.
    Draw a row at random, draw a query window around it, and count the bytes
    that the window reads. The mean converges to this value.
    An earlier rule sampled twenty windows from a fixed seed.
    On real files, a different seed could change the verdict.
    The formula calculates the limit of that sample.
    It needs no seed, window count, or draw order.

[^grid]: Validators need the same reference grid to produce comparable
    efficiency scores. Different tilings still give different skip rates,
    although the box-scaled window reduces the difference from the
    extent-scaled window. At n = 8, strips skip 0.864 and the grid skips 0.858.
    The vectors `five-strips-n5` and `three-boxes-old-vs-new-reference` test
    the required grid.

[^pruning]: Spatial order lets readers prune data.
    The footer boxes provide enough information to estimate this benefit.
    The pass bar is relative because the achievable skip rate rises with the
    row-group count. With two row groups, a reader can never skip more than half a file.
    Five hundred can skip about 98%.
    The 0.65 bar comes from the
    [calibration corpus](spatial-order/calibration/README.md).
    The survey used this metric in November 2026 on 5,914 files from 74
    registry catalogs. Hilbert-sorted copies of the tested low scorers with
    eight or more row groups scored 0.696 to 0.944.
    The one file that a sort improved from below 0.70 scored 0.668 before the
    sort and 0.912 after it.

[^floor]: A grid is a poor model of a curve sort at small row-group counts.
    Each half of a curve can span most of the extent.
    In the row-check calibration, Hilbert-sorted rows failed the footer check
    in 70% of files at two row groups, 13% at four, 2% at eight, and 0.2% at
    sixteen. The row check uses ten chunks, which behave like eight to ten
    row groups.

[^overlap]: A space-filling-curve sort places neighboring row groups next to
    each other in space. Their boxes share boundaries, so the overlap fraction can be
    near 1.0 even for a file whose boxes tile the extent.

[^pagestats]: A reader with page-level statistics can skip individual pages
    within row groups. The row-group read share overstates how much data
    that reader needs to fetch.
    A refined read share provides more information beside the verdict,
    as do the 1% and 25% windows.
