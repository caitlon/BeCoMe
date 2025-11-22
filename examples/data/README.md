# BeCoMe Case Study Datasets

This directory contains three real-world case study datasets from Czech public policy domain used to demonstrate and validate the BeCoMe (Best Compromise Mean) method. These datasets are part of a bachelor thesis at the Faculty of Economics and Management, Czech University of Life Sciences Prague.

## Overview

All datasets represent expert opinions collected during the COVID-19 pandemic period in the Czech Republic. Experts expressed their assessments as fuzzy triangular numbers (except Pendlers case, which uses crisp Likert scale values) to capture uncertainty and variability in their judgments.

**Key characteristics:**
- **Domain**: Public policy decision-making
- **Context**: COVID-19 pandemic emergency responses
- **Expert types**: Government officials, emergency service leaders, specialists
- **Format**: Text files with structured expert opinions
- **Purpose**: Thesis validation and BeCoMe method demonstration

## Dataset Overview

| Dataset | File | Experts | Type | Domain | Key Feature |
|---------|------|---------|------|--------|-------------|
| **Budget** | [budget_case.txt](budget_case.txt) | 22 (even) | Fuzzy intervals | Financial support | Moderate consensus |
| **Floods** | [floods_case.txt](floods_case.txt) | 13 (odd) | Fuzzy intervals | Flood prevention | Polarized opinions |
| **Pendlers** | [pendlers_case.txt](pendlers_case.txt) | 22 (even) | Likert scale | Travel policy | Crisp values |

---

## File Format Specification

### General Structure

All data files follow a standardized text format:

```
CASE: [CaseName]
DESCRIPTION: [Detailed description of the scenario]
EXPERTS: [Number]

# Format: ExpertID | Lower | Peak | Upper
[ExpertID] | [A] | [C] | [B]
[ExpertID] | [A] | [C] | [B]
...
```

### Field Descriptions

#### Header Fields

- **CASE**: Case study name (Budget, Floods, Pendlers)
- **DESCRIPTION**: Scenario description and question posed to experts
- **EXPERTS**: Total number of expert opinions (M)

#### Data Fields

Each expert opinion is represented as a fuzzy triangular number with three characteristic values:

| Field | Symbol | Description | Interpretation |
|-------|--------|-------------|----------------|
| **ExpertID** | - | Expert identifier | Name, title, or role |
| **Lower** | A | Lower bound | Pessimistic estimate (minimum) |
| **Peak** | C | Peak value | Most likely estimate (mode) |
| **Upper** | B | Upper bound | Optimistic estimate (maximum) |

**Constraint:** For all valid fuzzy numbers: `Lower ≤ Peak ≤ Upper` (A ≤ C ≤ B)

**Special case (Likert scale):** Crisp values where `Lower = Peak = Upper`

### Encoding

- **Format**: Plain text (UTF-8)
- **Line endings**: Unix-style (LF)
- **Separator**: Pipe character (`|`) with surrounding spaces
- **Comments**: Lines starting with `#`

---

## Individual Datasets

### 1. Budget Case

**File:** [budget_case.txt](budget_case.txt)

**Scenario:** COVID-19 pandemic budget support estimation

**Question:** "What level of state budget support and total financial support (in billions CZK) should be provided for entrepreneurs affected by the COVID-19 pandemic?"

**Range:** 0-100 billion CZK

**Expert panel:**
- 22 experts (even number)
- Government officials: Chairman, Deputy Ministers from multiple ministries
- Emergency services: Police President, Fire Rescue Director, Chief of General Staff
- Health authorities: Chief hygienist, Director of State Health Institute
- Cybersecurity: Director of NÚKIB

**Data characteristics:**
- **Expert count:** 22 (M = 22, even)
- **Opinion type:** Fuzzy triangular numbers
- **Value range:** 0-100 (billion CZK)
- **Consensus level:** Moderate agreement
- **Special features:** Wide range of estimates reflecting different ministry priorities

**Example opinions:**
```
Chairman | 40 | 70 | 90
Deputy Minister of MI | 60 | 90 | 90
Deputy Minister of MEYS | 15 | 40 | 60
```

**Key observations:**
- Interior Ministry (MI) proposes higher support (60-90-90)
- Education Ministry (MEYS) proposes lower support (15-40-60)
- Reflects different ministry budgets and pandemic impact on sectors

---

### 2. Floods Case

**File:** [floods_case.txt](floods_case.txt)

**Scenario:** Flood prevention planning - arable land reduction

**Question:** "What percentage reduction of arable land in flood areas is recommended to prevent floods?"

**Range:** 0-50% of arable land

**Expert panel:**
- 13 experts (odd number)
- Hydrologists and risk management specialists
- Land use planners and nature protection experts
- Municipality representatives
- Economists
- Emergency coordinators (rescue services)
- Land owners (directly affected stakeholders)

**Data characteristics:**
- **Expert count:** 13 (M = 13, odd)
- **Opinion type:** Fuzzy triangular numbers
- **Value range:** 0-50 (percentage)
- **Consensus level:** Highly polarized
- **Special features:** Demonstrates outlier handling and stakeholder conflict

**Example opinions:**
```
Hydrologist 1 | 37 | 42 | 47          (High reduction)
Land owner 1 | 2 | 3 | 4              (Low reduction)
Land owner 2 | 0 | 0 | 2              (Minimal reduction)
```

**Key observations:**
- **High reduction group** (37-50%): Hydrologists, rescue coordinators, municipalities
  - Prioritize flood prevention and public safety
- **Low reduction group** (0-11%): Land owners, nature protection, land use planners
  - Concerned about economic impact and land use changes
- **Middle group** (10-20%): Economists, some municipalities
  - Balancing safety and economic considerations

**Academic significance:** Demonstrates BeCoMe robustness with polarized opinions

---

### 3. Pendlers Case

**File:** [pendlers_case.txt](pendlers_case.txt)

**Scenario:** Cross-border travel policy during pandemic

**Statement:** "I agree that cross-border travel should be allowed for those who regularly travel from one country to another to work."

**Scale:** Likert scale (0-25-50-75-100)
- **0** = Strongly disagree
- **25** = Rather disagree
- **50** = Neutral
- **75** = Rather agree
- **100** = Strongly agree

**Expert panel:**
- 22 experts (even number)
- Same panel as Budget case (government officials and emergency services)

**Data characteristics:**
- **Expert count:** 22 (M = 22, even)
- **Opinion type:** Crisp values (special case of fuzzy numbers)
- **Value range:** {0, 25, 50, 75, 100} (discrete Likert scale)
- **Consensus level:** Mixed opinions
- **Special features:** Demonstrates handling of crisp values as degenerate fuzzy numbers

**Example opinions:**
```
Deputy Minister of MFA | 100 | 100 | 100    (Strongly agree)
Deputy Minister of MI | 0 | 0 | 0           (Strongly disagree)
Deputy Minister of MF | 50 | 50 | 50        (Neutral)
```

**Opinion distribution:**
- **Strongly disagree (0):** 4 experts (Interior, Defense, Agriculture, Chief hygienist)
- **Rather disagree (25):** 11 experts (majority)
- **Neutral (50):** 3 experts
- **Rather agree (75):** 4 experts (Labor, Justice, Industry)
- **Strongly agree (100):** 1 expert (Foreign Affairs)

**Key observations:**
- Foreign Affairs strongly supports (cross-border relations)
- Interior and Defense oppose (security concerns)
- Majority lean toward disagreement (pandemic restrictions)

**Academic significance:** Shows BeCoMe handling of Likert scale data (crisp values)

---

## Data Characteristics

### Summary Statistics

| Characteristic | Budget | Floods | Pendlers |
|----------------|--------|--------|----------|
| **Experts (M)** | 22 (even) | 13 (odd) | 22 (even) |
| **Data type** | Fuzzy | Fuzzy | Crisp |
| **Min value** | 10 | 0 | 0 |
| **Max value** | 90 | 50 | 100 |
| **Polarization** | Moderate | High | Moderate |
| **Use case** | Even median | Odd median | Likert scale |

### Methodological Significance

Each dataset demonstrates a specific aspect of the BeCoMe method:

1. **Budget Case** (even number of experts)
   - Demonstrates median calculation with even M
   - Shows averaging of two middle opinions after centroid sorting
   - Moderate consensus estimate

2. **Floods Case** (odd number of experts)
   - Demonstrates median calculation with odd M
   - Shows selection of middle opinion after centroid sorting
   - Robustness to polarized opinions and outliers

3. **Pendlers Case** (Likert scale)
   - Demonstrates handling of crisp values
   - Special case: fuzzy triangular numbers where A = C = B
   - Integration with Likert decision interpretation

---

## Using the Data

### Loading Data

The recommended way to load data is using the provided utility function:

```python
from examples.utils.data_loading import load_data_from_txt

# Load dataset
opinions, metadata = load_data_from_txt("examples/data/budget_case.txt")

# Access metadata
case_name = metadata["case"]          # "Budget"
description = metadata["description"]  # Case description
num_experts = len(opinions)           # 22

# Access expert opinions
for opinion in opinions:
    print(f"{opinion.expert_id}: {opinion.opinion}")
    print(f"  Centroid: {opinion.centroid}")
```

### Running Case Analysis

Pre-built analysis scripts are available for each dataset:

```bash
# Budget case (22 experts, even)
uv run python -m examples.analyze_budget_case

# Floods case (13 experts, odd)
uv run python -m examples.analyze_floods_case

# Pendlers case (22 experts, Likert scale)
uv run python -m examples.analyze_pendlers_case
```

See [../README.md](../README.md) for detailed usage instructions.

---

## Data Quality and Validation

### Validation Checks

All datasets have been validated for:

1. **Format compliance**
   - Correct header structure (CASE, DESCRIPTION, EXPERTS)
   - Proper data format (ExpertID | Lower | Peak | Upper)
   - UTF-8 encoding

2. **Data integrity**
   - Fuzzy number constraint: A ≤ C ≤ B for all opinions
   - Expert count matches EXPERTS header
   - No missing values

3. **Numerical precision**
   - All values are numeric
   - Values within reasonable ranges
   - Consistent decimal precision

### Reproducibility

All calculations on these datasets can be reproduced:

- **Excel reference implementation:** Validated against original Excel calculations (tolerance: 0.001)
- **Test coverage:** Integration tests in [../../tests/integration/test_excel_reference.py](../../tests/integration/test_excel_reference.py)
- **Expected results:** Stored in [../../tests/reference/](../../tests/reference/)

---

## Data Provenance

### Source

All datasets represent expert opinions collected during COVID-19 pandemic emergency planning sessions in the Czech Republic. The data has been anonymized where necessary while preserving expert roles and affiliations for context.

### Collection Period

- **Budget case:** COVID-19 pandemic emergency response (2020-2021)
- **Floods case:** Flood prevention policy discussions
- **Pendlers case:** Cross-border travel policy during pandemic restrictions

### Expert Anonymization

Expert identifiers preserve role information (e.g., "Deputy Minister of MI") while maintaining anonymity of specific individuals in accordance with research ethics guidelines.

---

## Limitations and Considerations

### Data Limitations

1. **Sample size:** Limited to 13-22 experts per case (not large-scale surveys)
2. **Context specificity:** Czech public policy during COVID-19 (may not generalize to other contexts)
3. **Time-bound:** Reflects situation at specific time during pandemic
4. **Expert panel:** Government officials and emergency services (specific perspective)

### Interpretation Guidelines

- **Budget case:** Estimates reflect ministry budgets and priorities, not objective economic analysis
- **Floods case:** Highly polarized due to stakeholder conflicts (land owners vs. safety experts)
- **Pendlers case:** Policy preferences, not health risk assessments

### Ethical Considerations

- Data collection followed institutional ethics guidelines
- Expert anonymization preserves confidentiality
- Results used for academic research and policy illustration only
- No sensitive personal information disclosed

---

## File Metadata

| File | Size | Lines | Format | Encoding |
|------|------|-------|--------|----------|
| budget_case.txt | 1.1 KB | 29 | Plain text | UTF-8 |
| floods_case.txt | 627 B | 20 | Plain text | UTF-8 |
| pendlers_case.txt | 1.3 KB | 30 | Plain text | UTF-8 |

---

## Related Documentation

### Project Documentation

- **Examples usage**: [../README.md](../README.md) - How to run case analyses
- **Method description**: [../../docs/method-description.md](../../docs/method-description.md) - BeCoMe mathematical foundation
- **Source code**: [../../src/README.md](../../src/README.md) - Implementation architecture
- **Tests**: [../../tests/README.md](../../tests/README.md) - Validation methodology

### Case Study Scripts

- [../analyze_budget_case.py](../analyze_budget_case.py) - Budget case analysis
- [../analyze_floods_case.py](../analyze_floods_case.py) - Floods case analysis
- [../analyze_pendlers_case.py](../analyze_pendlers_case.py) - Pendlers case analysis

### Visualizations

- [../visualizations/visualize_become.py](../visualizations/visualize_become.py) - Interactive visualizations for all cases
- [../visualizations/README.md](../visualizations/README.md) - Visualization documentation

---

## Academic Context

### Thesis Information

These datasets are part of a bachelor thesis titled "BeCoMe Method Implementation" at the Faculty of Economics and Management, Czech University of Life Sciences Prague.

**Purpose in thesis:**
- Demonstrate BeCoMe method application to real-world scenarios
- Validate implementation against different expert panel sizes (odd/even)
- Illustrate handling of diverse data types (fuzzy intervals, Likert scale)
- Show robustness to polarized opinions (Floods case)

### Research Reproducibility

All data and analysis scripts are provided for complete reproducibility:
- Raw data files in this directory
- Analysis scripts in [../](../)
- Expected results in [../../tests/reference/](../../tests/reference/)
- Validation tests in [../../tests/integration/](../../tests/integration/)

---

## Citation

If using these datasets in academic work, please cite:

```
Kuzmina, E. (2025-2026). BeCoMe Method Implementation
[Bachelor thesis]. Czech University of Life Sciences Prague,
Faculty of Economics and Management.
```

---

## Contact

For questions about the datasets or data access:

- **Author**: Ekaterina Kuzmina
- **Email**: xkuze010@studenti.czu.cz
- **University**: Czech University of Life Sciences Prague
- **Supervisor**: doc. Ing. Jan Tyrychtr, Ph.D.

---

## Notes

- All datasets use fuzzy triangular numbers except Pendlers (crisp Likert values)
- Files are human-readable text format for transparency
- Data validated against Excel reference implementation
- Expert roles preserved for context, individuals anonymized
- Designed for academic research and BeCoMe method demonstration
