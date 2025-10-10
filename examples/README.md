# BeCoMe Examples

This directory contains practical examples demonstrating how to use the BeCoMe (Best Compromise Mean) method for aggregating expert opinions.

## 📚 Available Examples

Three comprehensive examples that demonstrate step-by-step calculations with real-world case studies:

#### Budget Case (`analyze_budget_case.py`)
- **Scenario**: COVID-19 pandemic budget support estimation
- **Experts**: 22 (even number)
- **Data source**: `data/budget_case.txt`
- **Key feature**: Demonstrates median calculation with even number of experts

#### Floods Case (`analyze_floods_case.py`)
- **Scenario**: Flood prevention - arable land reduction percentage
- **Experts**: 13 (odd number)
- **Data source**: `data/floods_case.txt`
- **Key feature**: Demonstrates median calculation with odd number of experts and polarized opinions

#### Pendlers Case (`analyze_pendlers_case.py`)
- **Scenario**: Cross-border travel policy during pandemic
- **Experts**: 22 (even number)
- **Data source**: `data/pendlers_case.txt`
- **Key feature**: Demonstrates Likert scale data (crisp values as special case of fuzzy numbers)

**Run any analysis:**
```bash
python examples/analyze_budget_case.py
python examples/analyze_floods_case.py
python examples/analyze_pendlers_case.py
```

**What they show:**
- Loading data from text files
- Step-by-step calculation process
- Arithmetic mean (Gamma) calculation
- Median (Omega) calculation with sorting by centroids
- Best compromise (GammaOmegaMean) calculation
- Maximum error estimation
- Detailed formulas and intermediate results

---

## 📁 Data Files

The `data/` directory contains case study data in simple text format:

```
data/
├── budget_case.txt      # Budget support case (22 experts)
├── floods_case.txt      # Flood prevention case (13 experts)
└── pendlers_case.txt    # Cross-border travel case (22 experts)
```

### Text File Format

```
CASE: CaseName
DESCRIPTION: Case description text
EXPERTS: N

# Format: ExpertID | Lower | Peak | Upper
Expert1 | 10 | 15 | 20
Expert2 | 12 | 18 | 25
...
```

---

## 🚀 Quick Start

1. **Install dependencies:**
   ```bash
   pip install -e ".[dev]"
   ```

2. **Run any case analysis:**
   ```bash
   python examples/analyze_budget_case.py
   python examples/analyze_floods_case.py
   python examples/analyze_pendlers_case.py
   ```

---

## 📖 Learning Path

**Beginner:**
1. Start with `analyze_budget_case.py` to see a complete example
2. Study the step-by-step calculations and formulas
3. Read the code to understand how data is loaded from text files

**Intermediate:**
1. Run `analyze_floods_case.py` to see odd number of experts
2. Compare with `analyze_budget_case.py` (even number)
3. Understand median calculation differences

**Advanced:**
1. Run `analyze_pendlers_case.py` to see Likert scale handling
2. Compare all three analysis scripts
3. Understand how crisp values are special cases of fuzzy numbers
4. Create your own data files and run analysis

---

## 🔧 Using Your Own Data

To analyze your own expert opinions:

1. **Create a text file** in `data/` directory following the format above
2. **Copy an analysis script** (e.g., `analyze_budget_case.py`)
3. **Modify** to load your data file
4. **Run** and analyze results

Example:
```python
from examples.utils import load_data_from_txt

opinions, metadata = load_data_from_txt("examples/data/your_case.txt")
# ... rest of the analysis
```

---

## 📊 Understanding the Output

Each analysis script shows:

### Step 1: Arithmetic Mean (Γ)
- Formula: α = (1/M) × Σ(Ak), γ = (1/M) × Σ(Ck), β = (1/M) × Σ(Bk)
- Average of lower bounds, peaks, and upper bounds

### Step 2: Median (Ω)
- Opinions sorted by centroid values
- For odd M: middle element
- For even M: average of two middle elements

### Step 3: Best Compromise (ΓΩMean)
- Formula: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2
- Average of arithmetic mean and median

### Step 4: Maximum Error (Δmax)
- Formula: Δmax = |centroid(Γ) - centroid(Ω)| / 2
- Precision indicator (lower is better)

---

## 📚 References

For more information about the BeCoMe method, see:
- `../docs/method-description.md` - Mathematical foundation
- Main README.md - Project overview
- Original article in `../supplementary/article.tex`

---

## 🤝 Contributing

To add new examples:
1. Create a text file in `data/` with your case study
2. Create an analysis script following existing patterns
3. Update this README
4. Run tests to ensure everything works

