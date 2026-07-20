# Best Practices — Styling

Guidance for the visualization styles that [core](../portolan/core.md#visualization-styles)
requires. These are recommendations, not requirements.

- **Create multiple data-driven styles for rich collections.** If a collection has
  interesting categorical or numeric attributes, offer a style for each — e.g.
  buildings by age, by use, or by height. List the default first.

- **Vary default colors across a catalog** so it is not monotone. Use the subject
  matter as a guide: water in blues, vegetation in greens, the built environment in
  warm tones. Each collection should have a visually distinct default.

- **Use MapLibre GL expressions to reveal patterns.** Leverage `interpolate`,
  `match`, `case`, and `step` to encode data into color, and include a
  `description` explaining what the colors represent.

- **Consider labels.** For collections with named features (roads, monuments, admin
  areas), include a label layer or a dedicated "with labels" style variant.
