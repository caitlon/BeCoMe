# BeCoMe Examples

This directory contains practical examples demonstrating the BeCoMe (Best Compromise Mean) method for aggregating expert opinions. These examples are part of a bachelor thesis at the Faculty of Economics and Management, Czech University of Life Sciences Prague.

## Available Examples

Three comprehensive case studies demonstrate step-by-step calculations with real-world scenarios from Czech public policy domain:

### Budget Case (`analyze_budget_case.py`)
- **Scenario**: COVID-19 pandemic budget support estimation
- **Experts**: 22 (even number)
- **Data source**: `data/budget_case.txt`
- **Key feature**: Demonstrates median calculation with even number of experts

### Floods Case (`analyze_floods_case.py`)
- **Scenario**: Flood prevention - arable land reduction percentage
- **Experts**: 13 (odd number)
- **Data source**: `data/floods_case.txt`
- **Key feature**: Demonstrates median calculation with odd number of experts and polarized opinions

### Pendlers Case (`analyze_pendlers_case.py`)
- **Scenario**: Cross-border travel policy during pandemic
- **Experts**: 22 (even number)
- **Data source**: `data/pendlers_case.txt`
- **Key feature**: Demonstrates Likert scale data (crisp values as special case of fuzzy numbers)

### Running Examples

```bash
# COVID-19 budget support case
uv run python -m examples.analyze_budget_case

# Flood prevention case
uv run python -m examples.analyze_floods_case

# Cross-border travel policy case
uv run python -m examples.analyze_pendlers_case
```

Each example provides:
- Loading data from text files
- Step-by-step calculation process
- Arithmetic mean (Gamma) calculation
- Median (Omega) calculation with sorting by centroids
- Best compromise (GammaOmegaMean) calculation
- Maximum error estimation
- Detailed formulas and intermediate results

## Visualizations

The `visualizations/` directory contains interactive Jupyter notebooks with comprehensive visualizations for exploring BeCoMe results.

### Interactive Visualizations (`visualizations/visualize_become.py`)

Available visualization types:
- **Triangular Membership Functions** - Display expert opinions as fuzzy triangular numbers
- **Centroid Charts** - Compare expert centroids with aggregated metrics
- **Opinion Range Bars** - Horizontal bars showing opinion ranges, color-coded by distance from consensus
- **Interactive Sensitivity Analysis** - Dynamic exploration of expert inclusion/exclusion impact
- **Scenario Dashboard** - Comparative overview of all case studies
- **Accuracy Gauge Indicators** - Visual quality assessment of expert agreement

### Running Visualizations

```bash
jupyter notebook examples/visualizations/visualize_become.py
# or
jupyter lab examples/visualizations/visualize_become.py
```

All visualizations are automatically saved to `examples/visualizations/output/`.

## Data Files

The `data/` directory contains case study data in simple text format:

```
data/
├── budget_case.txt      # Budget support case (22 experts)
├── floods_case.txt      # Flood prevention case (13 experts)
└── pendlers_case.txt    # Cross-border travel case (22 experts)
```

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

Where:
- **Lower** - Pessimistic estimate (lower bound of fuzzy triangular number)
- **Peak** - Most likely value (peak of fuzzy triangular number)
- **Upper** - Optimistic estimate (upper bound of fuzzy triangular number)

## Usage

### Installation

Ensure dependencies are installed:

```bash
uv sync
# or
pip install -e ".[dev]"
```

### Running Case Analysis

```bash
uv run python -m examples.analyze_budget_case
uv run python -m examples.analyze_floods_case
uv run python -m examples.analyze_pendlers_case
```

### Using Custom Data

To analyze custom expert opinions:

1. Create a text file in `data/` directory following the format above
2. Copy an existing analysis script (e.g., `analyze_budget_case.py`)
3. Modify the script to load your data file
4. Run the analysis

Example code:

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

## Learning Path

### Beginner Level

1. Start with `analyze_budget_case.py` to see a complete example
2. Study the step-by-step calculations and formulas displayed in the output
3. Read the source code to understand how data is loaded from text files

### Intermediate Level

1. Run `analyze_floods_case.py` to see odd number of experts scenario
2. Compare output with `analyze_budget_case.py` (even number scenario)
3. Understand the differences in median calculation for odd vs. even expert counts

### Advanced Level

1. Run `analyze_pendlers_case.py` to see Likert scale handling
2. Compare all three analysis scripts to understand code patterns
3. Understand how crisp values (Likert scale) are special cases of fuzzy numbers
4. Create custom data files and run analysis on new scenarios

## Understanding the Output

Each analysis script displays the following calculation steps:

### Step 1: Arithmetic Mean (Γ)

Formula: α = (1/M) × Σ(Aₖ), γ = (1/M) × Σ(Cₖ), β = (1/M) × Σ(Bₖ)

Calculates the component-wise average of all expert opinions:
- Average of lower bounds
- Average of peaks
- Average of upper bounds

### Step 2: Median (Ω)

Expert opinions are sorted by centroid values, then:
- For odd M: median is the middle element
- For even M: median is the average of two middle elements

### Step 3: Best Compromise (ΓΩMean)

Formula: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2

Calculates the average of arithmetic mean and median, combining:
- Central tendency preservation (from arithmetic mean)
- Robustness to outliers (from median)

### Step 4: Maximum Error (Δmax)

Formula: Δmax = |centroid(Γ) - centroid(Ω)| / 2

Provides a precision indicator:
- Lower values indicate better agreement between mean and median
- Higher values suggest more dispersion in expert opinions

## References

For detailed information about the BeCoMe method:

- **Mathematical foundation**: See `../docs/method-description.md` for complete formulas and theoretical background
- **Project overview**: See `../README.md` for installation and general information
- **API documentation**: See `../docs/api-reference.md` for programmatic usage

## Example Output Structure

Each analysis script produces:

1. **Case header** with scenario description and expert count
2. **Step-by-step calculations** with intermediate values
3. **Visual representation** of expert opinions (when applicable)
4. **Final results** with best compromise and quality metrics
5. **Interpretation** of results in context of the scenario

All outputs are designed to be reproducible and facilitate understanding of the BeCoMe method's operation.
