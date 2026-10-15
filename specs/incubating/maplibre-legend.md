# Incubating — Legend Metadata for MapLibre GL Styles

**Status: proposed, adopted from a shipped implementation ([#118](https://github.com/portolan-sdi/portolan-spec/issues/118)).**

A MapLibre GL style encodes a thematic classification as one data-driven paint
expression. The expression holds every class color and every raw field value, so a
client can derive a legend from it without extra metadata. What the expression does
not hold is wording. A `match` on a `class` column yields entries labelled `res` and
`ind`, and the layer has no title beyond its `id`.

Styled Layer Descriptor has no equivalent gap, because there each class is a `Rule`
with its own `Title` and `Filter`. The legend falls out of the rule list, which is why
WMS can offer `GetLegendGraphic`. MapLibre collapses those rules into a single
expression, and the titles have nowhere to go.

This document specifies `metadata.legend`, a small object on a style layer that
carries the title and the display labels. It matches
[maplibre-legend](https://github.com/mvt-proj/maplibre-legend), the Rust crate that
already reads this key, so a style following this document renders in an existing
tool rather than one written for Portolan.

## The Unprefixed Key

The MapLibre GL style specification defines `metadata` as free-form on `$root` and on
each layer, and advises prefixing properties to avoid collisions. This convention uses
the bare `legend` key anyway, because maplibre-legend 0.5.1 reads that key today and a
second prefixed key would split a convention that has one implementation.

The cost is a genuine collision risk. Any other producer writing `metadata.legend`
under a different shape will break a reader that expects this one. Resolving that is a
condition of leaving incubation.

## Scope

This applies to a MapLibre GL style document following style specification v8. It
defines no new top-level fields and needs no change to MapLibre GL JS, which ignores
`metadata` entirely. Nothing below is specific to Portolan, and the document is written
so it can move to a repository of its own.

## Where the Legend Object Lives

The object sits at `layers[*].metadata.legend`. Every field in it is optional. This
document defines nothing on the style's root `metadata`.

```json
{
  "id": "land-use",
  "type": "fill",
  "source": "data",
  "source-layer": "parcels",
  "metadata": {
    "legend": {
      "label": "Land use",
      "default": "Other",
      "custom-labels": ["Residential", "Commercial", "Industrial"]
    }
  },
  "paint": {
    "fill-color": [
      "match", ["get", "class"],
      "res", "#e41a1c",
      "com", "#377eb8",
      "ind", "#4daf4a",
      "#cccccc"
    ]
  }
}
```

That layer renders as a block titled "Land use" holding four entries: Residential,
Commercial, Industrial, and Other against the fallback gray.

## Fields

| Field | Type | Applies to | When absent |
| ----- | ---- | ---------- | ----------- |
| `label` | string | the layer's legend block, as its title | falls back to `layer.id` |
| `default` | string | the fallback entry of a `match` or `case` expression | falls back to `layer.id` |
| `custom-labels` | array of string | the generated entries, in order | each entry keeps its derived label |

A `legend` member that is present but not a JSON object is an error, not something to
ignore. The hyphen in `custom-labels` is not a house convention. It is the key the
reference implementation reads.

## How Labels Are Assigned

A reader walks the layer's color expression and produces an ordered list of entries,
each one a color and a label. It holds a single index that starts at zero and advances
by one per entry. The entry at index *i* takes `custom-labels[i]` where that index
exists, and its derived label otherwise. Where the expression has a fallback arm, that
entry comes last and consumes the next index.

A shorter array is legal. Entries past its end fall back to derived labels, so a
publisher can name the first few classes and leave the rest.

The array is positional and carries no keys, which makes it fragile in one specific
way. Inserting a stop into the paint expression shifts every later label onto the wrong
entry, and nothing in the document reports the mismatch. Re-check the array in the same
commit that edits an expression.

## Derived Labels by Expression

| Expression | One entry per | Derived label | Fallback entry |
| ---------- | ------------- | ------------- | -------------- |
| `match` | value arm | the arm's value, stringified | yes, labelled from `default` |
| `case` | condition arm | the condition as text, such as `has height`, `without height`, or `class == res` | only when the array length is even |
| `interpolate` | stop | `{field} ≥ {stop}` | none |
| `step` | stop | `{field} < {first}`, then `{lower} ≤ {field} < {upper}`, and `{field} ≥ {last}` for the last | none |
| `coalesce` | delegated | the first argument that is one of the four above and yields more than one entry | as delegated |
| `literal` | one | the layer label | none |

A paint value that is a plain string, number, or boolean produces one entry carrying
the layer label.

Three constraints follow from the reference implementation and are worth stating,
because a style can be valid MapLibre and still fail to produce a legend:

- A `match` arm takes a single string or number. An arm listing several values as an
  array is rejected.
- `interpolate` and `step` read the field name from their input expression, which has
  to be `["get", "<field>"]`.
- `match` and `interpolate` need at least four elements. `step` needs at least three,
  and an even length above three is rejected as an incomplete threshold-color pair.

## Which Paint Property Is Read

| Layer type | Property read | Notes |
| ---------- | ------------- | ----- |
| `fill` | `fill-color` | also reads `fill-opacity` and `fill-outline-color` for the swatch |
| `line` | `line-color` | |
| `circle` | `circle-color` | also reads `circle-stroke-color` |
| `fill-extrusion` | `fill-extrusion-color` | |
| `background` | `background-color` | also reads `background-opacity` |
| `symbol` | layout `icon-image` and `text-field` | |
| `heatmap` | none | one entry carrying the layer label |
| `raster` | none | one entry carrying the layer label |
| any other type | none | one gray entry carrying the layer label |

`fill`, `line`, and `circle` require a `paint` object, and a reader errors without one.
For `fill-extrusion` and `background`, a missing `paint` falls back to the single gray
entry.

Only the types that read a color expression make use of `custom-labels` and `default`.
On the rest, `label` is the sole field that changes anything.

## Conformance

A producer:

- SHOULD set `label` on every layer meant to appear in a legend.
- SHOULD set `custom-labels` wherever the derived labels would be raw field values.
- MUST order `custom-labels` to match the entry order the expression produces.
- MUST NOT expect `default` to do anything on an `interpolate` or `step` expression,
  neither of which produces a fallback entry.

A reader:

- MUST fall back to `layer.id` for `label` and for `default` when either is absent.
- MUST apply `custom-labels` positionally, and fall back to the derived label for any
  entry past the end of the array.
- SHOULD ignore any member of `legend` it does not recognize.

## Reference Implementation

[maplibre-legend](https://github.com/mvt-proj/maplibre-legend) renders SVG legends from
a style document. It is a Rust crate under BSD-3-Clause, and version 0.5.1 is the
behavior described here. Every rule above was read from `src/common.rs` and the
per-layer modules on `main` in August 2026. It is the only shipped tool known to read
`metadata.legend`.

## Relationship to Portolan

Portolan requires a MapLibre GL style asset for every collection publishing PMTiles
(see [Visualization Styles](../portolan/core.md#visualization-styles) and
[`formats.md`](../portolan/formats.md)). Nothing in this document is required. A
collection whose styles carry `metadata.legend` gets a titled, labelled legend in a
client that reads the key, and behaves exactly as before in one that does not.

Graduating this into `formats.md` needs a decision on the unprefixed key and a second
independent implementation. Discussion is in
[#118](https://github.com/portolan-sdi/portolan-spec/issues/118).
