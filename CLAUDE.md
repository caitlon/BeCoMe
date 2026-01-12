# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## MCP Tools Usage

**Always use MCP tools proactively without being asked:**

- **context7**: Use automatically when code generation, setup/configuration steps, or library/API documentation is needed. Resolve library IDs and fetch docs without explicit user request.
- **sequential-thinking**: Use for breaking down complex problems or planning multi-step implementations.
- **ide**: Check diagnostics periodically when working with code to catch errors early. Use `executeCode` for Jupyter notebook operations.

## Git Workflow

**Git modification operations are DISABLED in settings.** Claude can only read:
- `git status` — view working tree status
- `git diff` — view changes
- `git log` — view commit history

**Commits must be done manually by the user.** When changes are ready, suggest a commit message in English using conventional commits format:
- Format: `<type>: <short description>` (max 50 characters)
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- Examples: `feat: add kennard-stone splitting`, `fix: correct median calculation`, `docs: update API reference`

## Writing Style for Comments, Documentation, and README

**Follow the writing guidelines in `supplementary/rules.md`** when writing:
- Code comments and docstrings
- README files and documentation
- Any user-facing text or explanations

**Key principles:**
1. **Vary sentence length** — mix short, medium, and long sentences (burstiness)
2. **Avoid AI patterns** — no "not X, but Y", no "it's important to note", no "moreover/furthermore"
3. **Natural transitions** — don't start every sentence with formal connectors
4. **Personal voice** — use specific examples, show personality, avoid generic statements
5. **No template structures** — break symmetry, vary paragraph lengths
6. **Minimal bullet points** — prefer narrative text over lists in documentation

**Never use these phrases:**
- "It's not just X, it's Y"
- "Moreover", "Furthermore", "Additionally" (at every turn)
- "In today's world", "In the realm of"
- "It's important to note that"
- "Delve", "navigate", "landscape" (as metaphors)

## Project Overview

**BeCoMe (Best Compromise Mean)** — Python implementation of a group decision-making method under fuzzy uncertainty.

The method aggregates expert opinions expressed as fuzzy triangular numbers **A** = (a, c, b):
- **a** = lower bound (pessimistic estimate)
- **c** = peak (most likely value)
- **b** = upper bound (optimistic estimate)

Algorithm steps:
1. **Arithmetic Mean (Γ)**: Component-wise average of all expert opinions
2. **Median (Ω)**: Sort by centroid, compute median fuzzy number
3. **Best Compromise (ΓΩMean)**: Average of arithmetic mean and median
4. **Error Estimation (Δmax)**: Maximum deviation as quality metric

### Case Studies

Three real-world datasets from Czech public policy:
- **budget_case** — COVID-19 budget support (22 experts)
- **floods_case** — Flood prevention planning (13 experts, polarized)
- **pendlers_case** — Cross-border travel policy (22 experts, Likert scale)

## Commands

### Running Examples

```bash
# COVID-19 budget case (22 experts, even number)
uv run python -m examples.analyze_budget_case

# Flood prevention case (13 experts, odd number)
uv run python -m examples.analyze_floods_case

# Cross-border travel case (22 experts, Likert scale)
uv run python -m examples.analyze_pendlers_case
```

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=src --cov-report=term-missing

# Run specific test categories
uv run pytest tests/unit/              # Unit tests only
uv run pytest tests/integration/       # Integration tests only
```

### Linting and Formatting

Ruff runs automatically via hooks after Edit/Write operations on .py files.

```bash
# Manual linting
uv run ruff check src/
uv run ruff format src/

# Type checking (strict mode)
uv run mypy src/ examples/

# Run all quality checks
uv run mypy src/ examples/ && uv run ruff check . && uv run pytest --cov=src
```

### Installation

```bash
# Sync all dependencies including dev
uv sync --extra dev

# Run scripts within venv
uv run python -m examples.analyze_budget_case
uv run pytest tests/
```

## Architecture

```
src/
├── models/                  # Data models
│   ├── fuzzy_number.py          # FuzzyTriangleNumber (a, c, b)
│   ├── expert_opinion.py        # ExpertOpinion with name and fuzzy number
│   └── become_result.py         # BeCoMeResult with all calculation outputs
├── calculators/             # Calculation logic
│   ├── become_calculator.py     # Main BeCoMe calculator
│   ├── base_calculator.py       # Abstract base class (Template Method)
│   └── median_strategies.py     # Strategy pattern for odd/even median
├── interpreters/            # Result interpretation
│   └── likert_interpreter.py    # Likert scale decision interpreter
└── exceptions.py            # Custom exceptions
```

### Key Patterns

- **Value Object**: `FuzzyTriangleNumber` is immutable and validated on construction
- **Strategy Pattern**: Different median calculation for odd/even expert counts
- **Template Method**: `BaseAggregationCalculator` defines calculation skeleton
- **Data Transfer Object**: `BeCoMeResult` encapsulates all calculation outputs

## API Usage

```python
from src.calculators.become_calculator import BeCoMeCalculator
from src.models.expert_opinion import ExpertOpinion
from src.models.fuzzy_number import FuzzyTriangleNumber

# Create expert opinions as fuzzy triangular numbers
experts = [
    ExpertOpinion("Expert 1", FuzzyTriangleNumber(5.0, 10.0, 15.0)),
    ExpertOpinion("Expert 2", FuzzyTriangleNumber(8.0, 12.0, 18.0)),
    ExpertOpinion("Expert 3", FuzzyTriangleNumber(6.0, 11.0, 16.0)),
]

# Calculate best compromise
calculator = BeCoMeCalculator()
result = calculator.calculate_compromise(experts)

# Access results
print(f"Best Compromise: {result.best_compromise}")
print(f"Arithmetic Mean: {result.arithmetic_mean}")
print(f"Median: {result.median}")
print(f"Max Error: {result.max_error}")
```

## Code Style

- **Line length**: 100 characters
- **Python version**: 3.13+
- **Linter/Formatter**: ruff (runs automatically via hooks)
- **Type checking**: mypy in strict mode
- **All code, comments, and variable names must be in English**

## Refactoring Guidelines

When removing functionality or refactoring code, delete everything cleanly:
- No commented-out code blocks "for reference"
- No unused imports left behind
- No backward-compatibility shims or fallbacks
- No `_old`, `_deprecated` suffixes
- No `# TODO: remove later` comments — remove it now
- Update all tests that reference removed functionality
