# BeCoMe Examples

Three case studies from Czech public policy show the BeCoMe method in action. Each loads real expert data, walks through the calculation, and displays intermediate results.

## Directory Structure

```
examples/
├── analyze_budget_case.py      # COVID-19 budget (22 experts, even)
├── analyze_floods_case.py      # Flood prevention (13 experts, odd)
├── analyze_pendlers_case.py    # Cross-border travel (22 experts, Likert)
├── data/                       # Case study datasets
├── utils/                      # Data loading, display, formatting
└── visualizations/             # Interactive Jupyter charts
```

## Case Studies

**Budget Case** (`analyze_budget_case.py`) — 22 government officials estimated COVID-19 budget support needs in billions of CZK. With an even expert count, this case shows how the median averages two middle values.

**Floods Case** (`analyze_floods_case.py`) — Land owners, hydrologists, and rescue coordinators disagreed sharply on flood prevention measures. The 13 experts produced highly polarized opinions, making this case useful for understanding how BeCoMe handles outliers when expert count is odd.

**Pendlers Case** (`analyze_pendlers_case.py`) — Public health officials rated cross-border travel policies on a Likert scale (0, 25, 50, 75, 100). Unlike other cases, this one uses crisp values where lower bound equals peak equals upper bound.

### Running Examples

```bash
# COVID-19 budget support case
uv run python -m examples.analyze_budget_case

# Flood prevention case
uv run python -m examples.analyze_floods_case

# Cross-border travel policy case
uv run python -m examples.analyze_pendlers_case
```

Each script loads data from text files, calculates arithmetic mean (Γ), median (Ω), and best compromise (ΓΩMean), then displays formulas and intermediate results at every step.

## Visualizations

The `visualizations/` directory contains interactive Jupyter notebooks for exploring BeCoMe results. Available charts include triangular membership functions, centroid comparisons, sensitivity analysis (toggle experts on/off to see impact), and a scenario dashboard comparing all three cases side-by-side.

```bash
jupyter notebook examples/visualizations/visualize_become.py
```

See [visualizations/README.md](visualizations/README.md) for details.

## Data Files

The `data/` directory contains case study data in simple text format:

```
data/
├── README.md            # Complete dataset documentation
├── budget_case.txt      # Budget support case (22 experts)
├── floods_case.txt      # Flood prevention case (13 experts)
└── pendlers_case.txt    # Cross-border travel case (22 experts)
```

See [data/README.md](data/README.md) for dataset documentation, provenance, and validation details.

### Text File Format

All data files follow a standardized format:

```
CASE: CaseName
DESCRIPTION: Case description text
EXPERTS: N

# Format: ExpertID | Lower | Peak | Upper
Expert1 | 10 | 15 | 20
Expert2 | 12 | 18 | 25
...
```

Lower, Peak, Upper represent the fuzzy triangular number (pessimistic, most likely, optimistic estimates).

## Custom Data

To analyze your own expert opinions, create a text file in `data/` following the format above:

```python
from examples.utils.data_loading import load_data_from_txt
from src.calculators.become_calculator import BeCoMeCalculator

# Load data
opinions, metadata = load_data_from_txt("examples/data/your_case.txt")

# Calculate best compromise
calculator = BeCoMeCalculator()
result = calculator.calculate_compromise(opinions)

# Display results
print(f"Best Compromise: {result.best_compromise}")
print(f"Max Error: {result.max_error}")
```

## Understanding the Output

Each script displays four calculation steps: arithmetic mean (Γ), median (Ω), best compromise (ΓΩMean), and maximum error (Δmax). The output shows formulas, intermediate values, and sorted expert opinions at each stage. For the mathematical foundation behind these calculations, see [docs/method-description.md](../docs/method-description.md).

## Related Documentation

- [Main README](../README.md) — project overview and installation
- [Method description](../docs/method-description.md) — mathematical foundation
- [Source code](../src/README.md) — API documentation
