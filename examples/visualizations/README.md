# BeCoMe visualizations

Interactive Jupyter charts for exploring expert opinions and BeCoMe calculation results.
Everything runs locally and needs no external services.

## Interactive demo

![BeCoMe interactive visualizations demo](demo.gif)

*Expert opinions, centroid comparisons, and sensitivity analysis in action.*

## Available visualizations

**Triangular membership functions.** Expert opinions appear as overlapping triangular fuzzy
numbers, with the arithmetic mean (Γ), the median (Ω), and the best compromise (ΓΩMean) drawn
on top.

**Centroid charts.** Each expert's fuzzy opinion collapses to a single centroid value, sorted
and compared against the aggregated metrics. Useful for spotting outliers.

**Sensitivity analysis.** Toggle individual experts on and off with checkboxes to see how their
inclusion affects the final compromise. The chart recalculates in real time.

**Scenario dashboard.** All three case studies (Budget, Floods, Pendlers) side by side, with a
metrics table and compact charts for cross-case comparison.

**Accuracy gauge.** A speedometer-style indicator of how far the experts agree, color-coded
green, yellow, or red from the maximum error metric.

## Running

```bash
jupyter notebook examples/visualizations/visualize_become.ipynb
# or
jupyter lab examples/visualizations/visualize_become.ipynb
```

Requires a Jupyter environment. A plain `uv sync` installs the core dependency only, so ask
for the two extras this notebook needs:

```bash
uv sync --extra viz --extra notebook
```

## Interactive features

Charts render as static Matplotlib images. One view is interactive: the sensitivity analysis
carries an ipywidgets checkbox per expert and redraws as soon as you toggle one. The redraw
runs in the notebook kernel, and nothing calls an external service.

## Technical details

Built with Matplotlib, Seaborn, NumPy, pandas, and ipywidgets.

## Related documentation

- [examples/README.md](../README.md): case study analyses
- [data/README.md](../data/README.md): dataset documentation
- [docs/method-description.md](../../docs/method-description.md): mathematical foundation
