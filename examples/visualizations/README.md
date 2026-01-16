# BeCoMe Visualizations

Interactive Jupyter charts for exploring expert opinions and BeCoMe calculation results. All visualizations run locally — no external services required.

## Interactive Demo

![BeCoMe Interactive Visualizations Demo](demo.gif)

*Expert opinions, centroid comparisons, and sensitivity analysis in action.*

## Available Visualizations

**Triangular Membership Functions** — Expert opinions displayed as overlapping triangular fuzzy numbers with arithmetic mean (Γ), median (Ω), and best compromise (ΓΩMean) highlighted on top.

**Centroid Charts** — Each expert's fuzzy opinion reduced to a single centroid value, sorted and compared against aggregated metrics. Useful for spotting outliers.

**Sensitivity Analysis** — Toggle individual experts on/off with checkboxes to see how their inclusion affects the final compromise. Recalculates in real time.

**Scenario Dashboard** — All three case studies (Budget, Floods, Pendlers) side-by-side with metrics table and compact charts for cross-case comparison.

**Accuracy Gauge** — Speedometer-style indicator showing agreement level among experts. Color-coded green/yellow/red based on maximum error metric.

## Running

```bash
jupyter notebook examples/visualizations/visualize_become.py
# or
jupyter lab examples/visualizations/visualize_become.py
```

Requires Jupyter environment (`uv sync` installs all dependencies).

## Interactive Features

Charts support zoom, pan, and hover tooltips. Sensitivity analysis updates immediately when toggling experts. Works entirely in browser — no server calls.

## Technical Details

Built with Matplotlib, Seaborn, and ipywidgets. Tested with 100+ expert datasets. Color schemes optimized for both screen and print.

## Related Documentation

- [examples/README.md](../README.md) — case study analyses
- [data/README.md](../data/README.md) — dataset documentation
- [docs/method-description.md](../../docs/method-description.md) — mathematical foundation
