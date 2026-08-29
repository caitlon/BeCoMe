# Case study datasets

Three expert-opinion datasets from Czech public policy, collected during pandemic planning for
COVID-19. Each one demonstrates a different aspect of the BeCoMe method.

| Dataset | Experts | Type | Key feature |
|---------|---------|------|-------------|
| [budget_case.txt](budget_case.txt) | 22 (even) | Fuzzy intervals | Moderate consensus |
| [floods_case.txt](floods_case.txt) | 13 (odd) | Fuzzy intervals | Polarized opinions |
| [pendlers_case.txt](pendlers_case.txt) | 22 (even) | Likert scale | Crisp values |

## File format

```
CASE: CaseName
DESCRIPTION: Scenario description
EXPERTS: N

# Format: ExpertID | Lower | Peak | Upper
Expert1 | 10 | 15 | 20
Expert2 | 12 | 18 | 25
```

**Lower**, **Peak**, **Upper** form a fuzzy triangular number (pessimistic, most likely, optimistic). Constraint: Lower ≤ Peak ≤ Upper. For Likert scale data, all three values are equal.

## Datasets

### Budget case

Government officials estimated COVID-19 budget support needs (0-100 billion CZK). The 22-member panel included deputy ministers from multiple ministries, the Police President, Fire Rescue Director, and Chief Hygienist.

Opinions varied by ministry priorities: Interior proposed higher support (60-90 billion), and
Education suggested lower (15-40 billion). With an even expert count, the median calculation
averages the two middle values.

```
Chairman | 40 | 70 | 90
Deputy Minister of MI | 60 | 90 | 90
Deputy Minister of MEYS | 15 | 40 | 60
```

### Floods case

Experts debated what percentage of arable land should be converted for flood prevention. The 13
participants held sharply divided views: hydrologists, land owners, rescue coordinators, and
economists.

Hydrologists recommended 37-47% reduction. Land owners proposed 0-4%. That polarization makes the Floods case useful for demonstrating BeCoMe's outlier resistance.
With an odd expert count, the median is the middle element after sorting.

```
Hydrologist 1 | 37 | 42 | 47
Land owner 1 | 2 | 3 | 4
Land owner 2 | 0 | 0 | 2
```

### Pendlers case

Officials rated whether cross-border commuters should be allowed to travel during pandemic restrictions. Unlike other cases, responses used a Likert scale: 0 (strongly disagree), 25, 50, 75, 100 (strongly agree).

Foreign Affairs strongly supported travel (100). Interior and Defense opposed it (0). The majority leaned toward disagreement: 11 of 22 chose "rather disagree" (25). Likert values
are crisp, so Lower = Peak = Upper.

```
Deputy Minister of MFA | 100 | 100 | 100
Deputy Minister of MI | 0 | 0 | 0
Deputy Minister of MF | 50 | 50 | 50
```

## Loading data

```python
from examples.utils.data_loading import load_data_from_txt

opinions, metadata = load_data_from_txt("examples/data/budget_case.txt")

print(metadata["case"])  # "Budget"
print(len(opinions))  # 22
print(opinions[0].expert_id)  # "Chairman"
print(opinions[0].opinion)  # FuzzyTriangleNumber(40, 70, 90)
```

## Data quality

The loader and the integration tests validate each dataset for:
- Format compliance (header structure, pipe-separated values, UTF-8)
- Fuzzy number constraint (Lower ≤ Peak ≤ Upper)
- Numerical precision against original Excel calculations (tolerance: 0.001)

The expected results live in [../../tests/reference/](../../tests/reference/), and the tests
that compare against them are in
[../../tests/integration/test_excel_reference.py](../../tests/integration/test_excel_reference.py).

## Provenance

The expert opinions were collected during COVID-19 emergency planning in the Czech Republic.
The identifiers preserve roles, for example "Deputy Minister of MI", while keeping individuals
anonymous.

## Limitations

- Small samples (13-22 experts), not large-scale surveys
- A Czech policy context during COVID-19, which may not generalize
- Government officials and emergency services, a specific perspective
- Floods case reflects stakeholder conflict, not objective risk assessment

## Related documentation

- [examples/README.md](../README.md): running the case analyses
- [docs/method-description.md](../../docs/method-description.md): mathematical foundation
- [Main README](../../README.md): project overview and citation info
