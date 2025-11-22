# BeCoMe Documentation

This directory contains comprehensive technical and methodological documentation for the BeCoMe (Best Compromise Mean) implementation. The documentation is part of a bachelor thesis at the Faculty of Economics and Management, Czech University of Life Sciences Prague.

## Overview

The documentation covers all aspects of the BeCoMe method implementation:

- **Mathematical foundation** - Theoretical basis and formulas
- **System architecture** - Design decisions and patterns
- **API reference** - Complete implementation documentation
- **Visual architecture** - UML diagrams and workflows
- **Quality metrics** - Validation and testing results
- **Bibliography** - Academic references and cited sources

All documentation follows academic standards for reproducibility and clarity.

## Document Structure

### Core Documentation

#### [method-description.md](method-description.md) (491 lines)

**Mathematical Foundation of the BeCoMe Method**

Complete description of the BeCoMe method for aggregating expert opinions expressed as fuzzy triangular numbers.

**Contents:**
- Fuzzy triangular number representation
- Arithmetic mean (Γ) calculation
- Statistical median (Ω) calculation with odd/even strategies
- Best compromise (ΓΩMean) derivation
- Maximum error (Δmax) estimation
- Worked examples with formulas

**Key formulas:**
- Arithmetic mean: α = (1/M) × Σ(Aₖ), γ = (1/M) × Σ(Cₖ), β = (1/M) × Σ(Bₖ)
- Median: Centroid-based sorting with strategy selection
- Best compromise: π = (α + ρ)/2, φ = (γ + ω)/2, ξ = (β + σ)/2
- Maximum error: Δmax = |centroid(Γ) - centroid(Ω)| / 2

**Target audience:** Researchers, reviewers, anyone needing theoretical understanding

---

#### [architecture.md](architecture.md) (686 lines)

**System Architecture and Design Decisions**

Detailed explanation of architectural choices, design patterns, and implementation rationale.

**Contents:**
- Layered architecture overview
- Design principles (SOLID, immutability, type safety)
- Module structure (models → calculators → interpreters)
- Design patterns (Value Object, Strategy, Template Method, Factory)
- Technology choices (Python 3.13+, Pydantic, mypy)
- Design decisions and trade-offs
- Future considerations

**Key architectural principles:**
- Separation of concerns across layers
- Dependency flow (examples → calculators → models)
- No circular dependencies
- Testability and maintainability

**Target audience:** Developers, software architects, thesis reviewers

---

#### [api-reference.md](api-reference.md) (875 lines)

**Complete API Documentation**

Comprehensive reference for all classes, methods, and functions in the implementation.

**Contents:**
- `FuzzyTriangleNumber` - Fuzzy number representation
- `ExpertOpinion` - Expert opinion with identifier
- `BeCoMeResult` - Calculation results
- `BeCoMeCalculator` - Main calculator implementation
- `BaseAggregationCalculator` - Abstract base class
- `MedianCalculationStrategy` - Strategy pattern for median
- `LikertDecisionInterpreter` - Likert scale interpretation
- Usage examples for each component

**Documentation style:**
- Type signatures for all parameters
- Return types specified
- Exceptions documented
- Code examples included

**Target audience:** Developers using the library, API consumers

---

#### [uml-diagrams.md](uml-diagrams.md) (300 lines)

**Visual Architecture Documentation**

UML diagrams illustrating the static structure and dynamic behavior of the implementation.

**Contents:**
- **Class Diagram** - Static structure, relationships, attributes, methods
- **Sequence Diagram** - Calculation process flow
- **Activity Diagram** - Algorithm logic and decision points

**Diagram formats:**
- PNG images for viewing ([uml-diagrams/](uml-diagrams/))
- PlantUML source (.puml) for reproducibility and modification

**Target audience:** Visual learners, architecture reviewers, thesis committee

---

#### [quality-report.md](quality-report.md) (456 lines)

**Code Quality Metrics and Validation**

Comprehensive quality assurance report demonstrating implementation reliability.

**Contents:**
- Type checking (mypy strict mode: 100%)
- Linting (ruff: 100% compliance)
- Code formatting (ruff format: consistent)
- Test results (202 tests passing)
- Code coverage (100% line and branch coverage)
- Performance metrics

**Quality standards:**
- Zero type errors in strict mode
- No `type: ignore` suppressions
- Complete docstring coverage
- All edge cases tested

**Target audience:** Quality reviewers, thesis committee, maintainers

---

#### [references.md](references.md) (550 lines)

**Bibliography and Academic References**

Comprehensive bibliography for the BeCoMe implementation project, covering all sources cited in the bachelor thesis.

**Contents:**
- Core BeCoMe method references (Vrana2021, Prokopova2023)
- Fuzzy logic foundations (Zadeh1965, Bellman1970, Klir1995)
- Software engineering and architecture (Lott2021, Newman2021, Fielding2000, Kane2018)
- Czech academic sources (Subrt2011, Merunka2005)
- Complete BibTeX entries for reproducibility
- Citation context and usage in thesis chapters
- DOI links for peer-reviewed sources

**Reference categories:**
- 11 total references across 4 categories
- 3 journal articles (BeCoMe, fuzzy sets, decision-making)
- 6 books (software engineering, fuzzy logic, economic methods)
- 1 doctoral dissertation (REST architecture)
- 1 online article (BeCoMe public communication)

**Target audience:** Academic reviewers, thesis committee, researchers citing this work

---

### Supporting Files

#### [generate_diagrams.py](generate_diagrams.py) (66 lines)

**UML Diagram Generation Script**

Python script for generating UML diagrams from PlantUML source files.

**Purpose:**
- Demonstrates documentation workflow
- Ensures reproducibility of diagrams
- Allows diagram updates as code evolves

**Usage:**
```bash
python docs/generate_diagrams.py
```

**Dependencies:** PlantUML (requires Java runtime)

**Note:** This script is part of the documentation workflow for thesis reproducibility.

---

#### [uml-diagrams/](uml-diagrams/)

**UML Diagram Source Files and Images**

Contains both source (.puml) and rendered (.png) versions of all UML diagrams.

**Files:**
- `class-diagram.puml` / `class-diagram.png` - Static structure
- `sequence-diagram.puml` / `sequence-diagram.png` - Calculation flow
- `activity-diagram.puml` / `activity-diagram.png` - Algorithm logic

**Reproducibility:** PlantUML source files enable diagram regeneration and modification.

---

## Recommended Reading Order

### For First-Time Readers (Understanding the Method)

1. **[method-description.md](method-description.md)** - Start here to understand BeCoMe theory
2. **[uml-diagrams.md](uml-diagrams.md)** - Visual overview of the implementation
3. **[architecture.md](architecture.md)** - Design decisions and patterns
4. **[api-reference.md](api-reference.md)** - Implementation details
5. **[quality-report.md](quality-report.md)** - Validation and quality metrics

### For Thesis Reviewers (Academic Assessment)

1. **[method-description.md](method-description.md)** - Mathematical foundation
2. **[references.md](references.md)** - Bibliography and cited sources
3. **[quality-report.md](quality-report.md)** - Implementation quality (100% coverage)
4. **[architecture.md](architecture.md)** - Design rationale
5. **[uml-diagrams.md](uml-diagrams.md)** - Visual architecture

### For Developers (Using or Extending the Code)

1. **[api-reference.md](api-reference.md)** - Complete API documentation
2. **[architecture.md](architecture.md)** - Design patterns and structure
3. **[uml-diagrams.md](uml-diagrams.md)** - Visual class relationships
4. **[method-description.md](method-description.md)** - Algorithm details

### For Quick Reference (Finding Specific Information)

- **Formulas** → [method-description.md](method-description.md)
- **Class methods** → [api-reference.md](api-reference.md)
- **Design patterns** → [architecture.md](architecture.md)
- **Test coverage** → [quality-report.md](quality-report.md)
- **Class relationships** → [uml-diagrams.md](uml-diagrams.md)
- **Bibliography** → [references.md](references.md)

---

## Quick Reference Guide

### Mathematical Formulas

| Concept | Formula | Document |
|---------|---------|----------|
| Centroid | Gx = (A + C + B) / 3 | [method-description.md](method-description.md) |
| Arithmetic Mean | α = (1/M) × Σ(Aₖ) | [method-description.md](method-description.md) |
| Median (odd) | Middle element | [method-description.md](method-description.md) |
| Median (even) | Average of two middle | [method-description.md](method-description.md) |
| Best Compromise | (Γ + Ω) / 2 | [method-description.md](method-description.md) |
| Maximum Error | \|centroid(Γ) - centroid(Ω)\| / 2 | [method-description.md](method-description.md) |

### Key Classes

| Class | Purpose | Document |
|-------|---------|----------|
| `FuzzyTriangleNumber` | Fuzzy number representation | [api-reference.md](api-reference.md) |
| `ExpertOpinion` | Expert opinion container | [api-reference.md](api-reference.md) |
| `BeCoMeCalculator` | Main calculation engine | [api-reference.md](api-reference.md) |
| `BeCoMeResult` | Result encapsulation | [api-reference.md](api-reference.md) |
| `LikertDecisionInterpreter` | Likert scale interpretation | [api-reference.md](api-reference.md) |

### Design Patterns

| Pattern | Application | Document |
|---------|-------------|----------|
| Value Object | `FuzzyTriangleNumber`, `ExpertOpinion` | [architecture.md](architecture.md) |
| Strategy | Median calculation (odd/even) | [architecture.md](architecture.md) |
| Template Method | `BaseAggregationCalculator` | [architecture.md](architecture.md) |
| Factory Method | `BeCoMeResult.from_calculations()` | [architecture.md](architecture.md) |

---

## Related Documentation

### Project Documentation

- **Main README**: [../README.md](../README.md) - Project overview, installation, usage
- **Source code**: [../src/README.md](../src/README.md) - Source code architecture
- **Examples**: [../examples/README.md](../examples/README.md) - Case studies and tutorials
- **Tests**: [../tests/README.md](../tests/README.md) - Testing methodology and coverage
- **Visualizations**: [../examples/visualizations/README.md](../examples/visualizations/README.md) - Interactive charts

### Data Documentation

- **Data files**: [../examples/data/](../examples/data/) - Case study datasets
  - `budget_case.txt` - COVID-19 budget allocation (22 experts)
  - `floods_case.txt` - Flood prevention planning (13 experts)
  - `pendlers_case.txt` - Cross-border travel policy (22 experts)

**Note:** For detailed data documentation, see [../examples/data/README.md](../examples/data/README.md)

### Installation and Setup

For installation instructions, environment setup, and dependencies, refer to:
- [../README.md#installation](../README.md#installation) - Installation guide
- [../README.md#usage](../README.md#usage) - Basic usage examples

---

## Technical Details

### Documentation Formats

All documentation uses **Markdown** (.md) for compatibility and readability:
- Human-readable in plain text
- Renders properly on GitHub
- Compatible with static site generators (MkDocs, Sphinx)
- Version-controllable in Git

### UML Diagram Generation

UML diagrams are created using **PlantUML**:

**Source format:** `.puml` files (text-based, version-controllable)
**Output format:** `.png` images (for documentation inclusion)

**Regenerating diagrams:**
```bash
python docs/generate_diagrams.py
```

**Requirements:**
- PlantUML installed
- Java runtime environment

**Workflow:**
1. Edit `.puml` source files in [uml-diagrams/](uml-diagrams/)
2. Run `generate_diagrams.py` to create PNG images
3. Images automatically referenced in [uml-diagrams.md](uml-diagrams.md)

### Documentation Maintenance

**Update frequency:**
- `method-description.md` - Stable (mathematical foundation)
- `architecture.md` - Update when design changes
- `api-reference.md` - Update with code changes
- `uml-diagrams.md` - Regenerate when architecture changes
- `quality-report.md` - Update after quality checks

**Validation:**
- Ensure code examples in documentation work
- Verify links are not broken
- Check formulas match implementation
- Update version information

---

## Document Statistics

| Document | Lines | Size | Last Updated |
|----------|-------|------|--------------|
| method-description.md | 491 | 12 KB | 2025-10-12 |
| architecture.md | 686 | 18 KB | 2025-10-12 |
| api-reference.md | 875 | 20 KB | 2025-10-12 |
| uml-diagrams.md | 300 | 10 KB | 2025-10-12 |
| quality-report.md | 456 | 10 KB | 2025-10-12 |
| references.md | 605 | 22 KB | 2025-11-22 |
| **Total** | **3,413** | **92 KB** | - |

---

## Notes

### Academic Context

All documentation in this directory is part of a bachelor thesis submission at the Faculty of Economics and Management, Czech University of Life Sciences Prague. The documentation demonstrates:

- Thorough understanding of the BeCoMe method
- Professional software engineering practices
- Academic rigor in implementation and validation
- Reproducibility of research results

### Documentation Philosophy

The documentation follows these principles:

1. **Completeness** - All aspects of the implementation are documented
2. **Clarity** - Written for multiple audiences (researchers, developers, reviewers)
3. **Reproducibility** - Sufficient detail to replicate the work
4. **Professionalism** - Academic tone and formatting standards
5. **Maintainability** - Version-controlled, text-based formats

### For Thesis Committee

This documentation provides complete evidence of:

- Understanding of fuzzy number aggregation theory
- Application of software engineering best practices
- Validation through comprehensive testing
- Quality assurance through multiple metrics
- Reproducible research methodology

---

## Contact

For questions about the documentation or implementation:

- **Author**: Ekaterina Kuzmina
- **Email**: xkuze010@studenti.czu.cz
- **University**: Czech University of Life Sciences Prague
- **Faculty**: Faculty of Economics and Management (Provozně ekonomická fakulta)
- **Supervisor**: doc. Ing. Jan Tyrychtr, Ph.D.
