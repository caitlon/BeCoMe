# BeCoMe Bibliography and References

This document provides a comprehensive bibliography for the BeCoMe (Best Compromise Mean) implementation project. All references are cited in the theoretical foundations chapter of the bachelor thesis and support the mathematical, methodological, and software engineering aspects of this work.

## Overview

The bibliography encompasses three main areas:

1. **BeCoMe Method and Fuzzy Logic** - Theoretical foundations for fuzzy triangular numbers and group decision-making
2. **Software Engineering** - Object-oriented design, architecture patterns, and implementation frameworks
3. **Czech Academic Sources** - Economic-mathematical methods and system design methodology

All references are maintained in BibTeX format in [../supplementary/kapitoly/literatura.bib](../supplementary/kapitoly/literatura.bib) for reproducibility and academic citation management.

---

## Core References

### Primary BeCoMe Method Reference

**Vrana, I., Tyrychtr, J., & Pelikán, M. (2021)**

- **Title**: BeCoMe: Easy-to-implement optimized method for best-compromise group decision making: Flood-prevention and COVID-19 case studies
- **Journal**: *Environmental Modelling & Software*, Volume 136, Article 104953
- **DOI**: [10.1016/j.envsoft.2020.104953](https://doi.org/10.1016/j.envsoft.2020.104953)
- **Year**: 2021

**Significance**: This is the foundational paper that introduces the BeCoMe method. It describes:
- Mathematical formulation of the method
- Aggregation of expert opinions as fuzzy triangular numbers
- Calculation of arithmetic mean (Γ), statistical median (Ω), and best compromise (ΓΩMean)
- Maximum error estimation (Δmax)
- Real-world case studies (flood prevention, COVID-19 policy)
- Excel reference implementation (Appendix A)

**Usage in thesis**: Primary reference for the BeCoMe algorithm, mathematical formulas, and methodology. The implementation in this project validates against the Excel reference from this paper.

---

### Public Communication

**Prokopová, L. (2023)**

- **Title**: BeCoMe aneb Jak nalézt nejlepší možný kompromis v náročných situacích (BeCoMe: Finding the Best Possible Compromise in Difficult Situations)
- **Type**: Online article
- **URL**: [https://zivauni.cz/become-aneb-jak-nalezt-nejlepsi-mozny-kompromis-v-narocnych-situacich/](https://zivauni.cz/become-aneb-jak-nalezt-nejlepsi-mozny-kompromis-v-narocnych-situacich/)
- **Accessed**: 2025-09-27
- **Language**: Czech

**Significance**: Interview with doc. Ing. Jan Tyrychtr, Ph.D. (thesis supervisor) explaining the BeCoMe method's practical applications, including:
- Use in Czech Republic's Central Crisis Staff during COVID-19
- Handling polarized expert opinions
- Argument strength: "This decision represents the best possible compromise according to information theory"

**Usage in thesis**: Contextual understanding of BeCoMe's real-world applications and expert decision-making philosophy.

---

## Fuzzy Logic Foundations

### Foundational Fuzzy Set Theory

**Zadeh, L. A. (1965)**

- **Title**: Fuzzy Sets
- **Journal**: *Information and Control*, Volume 8, Number 3, Pages 338-353
- **DOI**: [10.1016/S0019-9958(65)90241-X](https://doi.org/10.1016/S0019-9958(65)90241-X)
- **Year**: 1965

**Significance**: The seminal paper that introduced fuzzy set theory. Zadeh defined:
- Membership functions with degrees of belonging [0, 1]
- Mathematical formalization of vague and imprecise concepts
- Fuzzy set operations (union, intersection, complement)
- Linguistic variables and approximate reasoning

**Usage in thesis**: Theoretical foundation for representing expert opinions as fuzzy triangular numbers. Cited as paradigm shift from classical set theory to fuzzy logic.

---

**Bellman, R. E., & Zadeh, L. A. (1970)**

- **Title**: Decision-Making in a Fuzzy Environment
- **Journal**: *Management Science*, Volume 17, Number 4, Pages B-141 to B-164
- **DOI**: [10.1287/mnsc.17.4.B141](https://doi.org/10.1287/mnsc.17.4.B141)
- **Year**: 1970

**Significance**: Formalized decision-making with fuzzy goals and constraints:
- Symmetric treatment of goals and constraints as fuzzy sets
- Optimization in uncertain environments
- Foundation for fuzzy decision support systems

**Usage in thesis**: Theoretical context for fuzzy decision-making. Contrasted with BeCoMe's statistical aggregation approach (minimum operator vs. statistical mean/median).

---

**Klir, G. J., & Yuan, B. (1995)**

- **Title**: Fuzzy Sets and Fuzzy Logic: Theory and Applications
- **Publisher**: Prentice Hall PTR
- **ISBN**: 9780131011717
- **Year**: 1995

**Significance**: Comprehensive textbook covering:
- Fuzzy set theory and operations
- Fuzzy numbers and linguistic variables
- Triangular membership functions
- Applications in decision-making and control

**Usage in thesis**: Reference for fuzzy triangular numbers, linguistic variables, and graphical representation of membership functions. Source for Figure 1.2 (triangular membership function).

---

## Software Engineering and Architecture

### Object-Oriented Programming

**Lott, S. F., & Phillips, D. (2021)**

- **Title**: Python Object-Oriented Programming: Build Robust and Maintainable Object-oriented Python Applications and Libraries
- **Edition**: Fourth
- **Publisher**: Packt Publishing
- **ISBN**: 9781801075237
- **Year**: 2021

**Significance**: Modern Python OOP practices including:
- Class design and inheritance
- Encapsulation, polymorphism, abstraction
- Design patterns in Python
- Type hints and validation (Pydantic)
- UML class diagrams

**Usage in thesis**: Guide for implementing BeCoMe using object-oriented principles. Source for Figure 1.5 (UML class diagram example with Orange/Basket classes). Referenced for analysis, design, and programming phases.

---

### Microservices Architecture

**Newman, S. (2021)**

- **Title**: Building Microservices: Designing Fine-Grained Systems
- **Edition**: Second
- **Publisher**: O'Reilly Media
- **ISBN**: 9781492033998
- **Year**: 2021

**Significance**: Microservices architectural patterns:
- Independent deployability principle
- Service decomposition by business domains
- Loose coupling and high cohesion
- Vertical slicing vs. horizontal layering

**Usage in thesis**: Architectural rationale for separating backend (Python/Flask) from frontend (React). Source for Figures 1.3 and 1.4 (monolithic vs. microservices architecture diagrams).

---

### REST Architecture

**Fielding, R. T. (2000)**

- **Title**: Architectural Styles and the Design of Network-based Software Architectures
- **Type**: Doctoral dissertation
- **School**: University of California, Irvine
- **Year**: 2000

**Significance**: Formal definition of REST (Representational State Transfer):
- Stateless client-server communication
- Uniform interface constraints
- Resource-based architecture
- Cacheability and layered system

**Usage in thesis**: Theoretical foundation for REST API design used for backend service. Source for Figure 5.10 (REST components and communication paths).

---

### Containerization

**Kane, S. P., & Matthias, K. (2018)**

- **Title**: Docker: Up & Running: Shipping Reliable Containers in Production
- **Edition**: Second
- **Publisher**: O'Reilly Media
- **ISBN**: 9781491918517
- **Year**: 2018

**Significance**: Docker containerization concepts:
- Application isolation and packaging
- Image/container lifecycle
- Docker registry and distribution
- Consistent deployment across environments

**Usage in thesis**: Containerization strategy for deploying frontend and backend services. Source for Figure 2.3 (Docker client-server architecture diagram).

---

## Czech Academic References

### Economic-Mathematical Methods

**Šubrt, T., Bartoška, J., Brožová, H., Dömeová, L., Houška, M., & Kučera, P. (2011)**

- **Title**: Ekonomicko-matematické metody (Economic-Mathematical Methods)
- **Publisher**: Vydavatelství a nakladatelství Aleš Čeněk, s.r.o.
- **Location**: Plzeň, Czech Republic
- **ISBN**: 978-80-7380-345-2
- **Year**: 2011
- **Language**: Czech

**Significance**: Czech textbook on economic decision-making methods:
- Multi-criteria decision analysis
- Decision-making under uncertainty (Wald criterion, maximax, Savage)
- Classical decision theory foundations

**Usage in thesis**: Context for BeCoMe within multi-criteria analysis paradigm. Referenced for decision-making criteria under complete uncertainty, contrasted with fuzzy approach.

---

### Object-Oriented System Design

**Merunka, V., Pergl, R., & Pícka, M. (2005)**

- **Title**: Objektově orientovaný přístup v projektování informačních systémů (Object-Oriented Approach in Information System Design)
- **Publisher**: Česká zemědělská univerzita v Praze (Czech University of Life Sciences Prague)
- **Location**: Praha (Prague), Czech Republic
- **Type**: Textbook (Skriptum)
- **Year**: 2005
- **Language**: Czech

**Significance**: Czech academic resource on OOP and system design:
- Semantic gap between human thinking and computer execution
- OOP principles: encapsulation, inheritance, polymorphism
- UML modeling (class diagrams, relationships, multiplicities)
- Aggregation vs. composition relationships

**Usage in thesis**: Theoretical foundation for object-oriented design from Faculty of Economics and Management, Czech University of Life Sciences Prague (thesis institution). Referenced for OOP principles and UML methodology.

---

## BibTeX Entries

All references are maintained in BibTeX format for citation management. The complete `.bib` file is available at:

**Location**: [../supplementary/kapitoly/literatura.bib](../supplementary/kapitoly/literatura.bib)

### Journal Articles

```bibtex
@article{Vrana2021,
  author  = {Vrana, Ivan and Tyrychtr, Jan and Pelikán, Martin},
  title   = {{BeCoMe: Easy-to-implement optimized method for best-compromise group decision making: Flood-prevention and COVID-19 case studies}},
  journal = {Environmental Modelling \& Software},
  year    = {2021},
  volume  = {136},
  pages   = {104953},
  doi     = {10.1016/j.envsoft.2020.104953}
}

@article{Zadeh1965,
  author  = {Zadeh, Lotfi A.},
  title   = {{Fuzzy Sets}},
  journal = {Information and Control},
  year    = {1965},
  volume  = {8},
  number  = {3},
  pages   = {338--353},
  doi     = {10.1016/S0019-9958(65)90241-X}
}

@article{Bellman1970,
  author  = {Bellman, Richard E. and Zadeh, Lotfi A.},
  title   = {{Decision-Making in a Fuzzy Environment}},
  journal = {Management Science},
  volume  = {17},
  number  = {4},
  pages   = {B-141--B-164},
  year    = {1970},
  doi     = {10.1287/mnsc.17.4.B141}
}
```

### Doctoral Dissertation

```bibtex
@phdthesis{Fielding2000,
  author  = {Fielding, Roy Thomas},
  title   = {{Architectural Styles and the Design of Network-based Software Architectures}},
  school  = {University of California, Irvine},
  year    = {2000},
  type    = {Doctoral dissertation}
}
```

### Books

```bibtex
@book{Klir1995,
  author    = {Klir, George J. and Yuan, Bo},
  title     = {{Fuzzy Sets and Fuzzy Logic: Theory and Applications}},
  publisher = {Prentice Hall PTR},
  year      = {1995},
  isbn      = {9780131011717}
}

@book{Lott2021,
  author    = {Lott, Steven F. and Phillips, Dusty},
  title     = {{Python Object-Oriented Programming: Build Robust and Maintainable Object-oriented Python Applications and Libraries}},
  edition   = {Fourth},
  publisher = {Packt Publishing},
  year      = {2021},
  isbn      = {9781801075237}
}

@book{Newman2021,
  author    = {Newman, Sam},
  title     = {{Building Microservices: Designing Fine-Grained Systems}},
  edition   = {Second},
  publisher = {O'Reilly Media},
  year      = {2021},
  isbn      = {9781492033998}
}

@book{Kane2018,
  author    = {Kane, Sean P. and Matthias, Karl},
  title     = {{Docker: Up \& Running: Shipping Reliable Containers in Production}},
  edition   = {Second},
  publisher = {O'Reilly Media},
  year      = {2018},
  isbn      = {9781491918517}
}

@book{Subrt2011,
  author    = {Šubrt, Tomáš and Bartoška, Jan and Brožová, Helena and Dömeová, Ludmila and Houška, Milan and Kučera, Petr},
  title     = {Ekonomicko-matematické metody},
  publisher = {Vydavatelství a nakladatelství Aleš Čeněk, s.r.o.},
  year      = {2011},
  address   = {Plzeň},
  isbn      = {978-80-7380-345-2}
}

@book{Merunka2005,
  author    = {Merunka, Vojtěch and Pergl, Robert and Pícka, Marek},
  title     = {Objektově orientovaný přístup v projektování informačních systémů},
  publisher = {Česká zemědělská univerzita v Praze},
  year      = {2005},
  address   = {Praha},
  note      = {Skriptum}
}
```

### Online Resources

```bibtex
@online{Prokopova2023,
  author    = {Prokopová, Lenka},
  title     = {{BeCoMe aneb Jak nalézt nejlepší možný kompromis v náročných situacích}},
  year      = {2023},
  url       = {https://zivauni.cz/become-aneb-jak-nalezt-nejlepsi-mozny-kompromis-v-narocnych-situacich/},
  urldate   = {2025-09-27}
}
```

---

## Reference Categories

### By Topic

| Category | References | Count |
|----------|-----------|-------|
| **BeCoMe Method** | Vrana2021, Prokopova2023 | 2 |
| **Fuzzy Logic** | Zadeh1965, Bellman1970, Klir1995 | 3 |
| **Software Engineering** | Lott2021, Newman2021, Fielding2000, Kane2018 | 4 |
| **Czech Academic** | Subrt2011, Merunka2005 | 2 |
| **Decision Theory** | Bellman1970, Subrt2011, Vrana2021 | 3 |

### By Publication Type

| Type | Count | References |
|------|-------|------------|
| **Journal Articles** | 3 | Vrana2021, Zadeh1965, Bellman1970 |
| **Books** | 6 | Klir1995, Lott2021, Newman2021, Kane2018, Subrt2011, Merunka2005 |
| **Dissertations** | 1 | Fielding2000 |
| **Online Articles** | 1 | Prokopova2023 |
| **Total** | **11** | |

### By Year

| Decade | References | Count |
|--------|-----------|-------|
| **1960s** | Zadeh1965 | 1 |
| **1970s** | Bellman1970 | 1 |
| **1990s** | Klir1995 | 1 |
| **2000s** | Fielding2000, Merunka2005 | 2 |
| **2010s** | Subrt2011, Kane2018 | 2 |
| **2020s** | Vrana2021, Lott2021, Newman2021, Prokopova2023 | 4 |

---

## Citation Context

### Where References Are Used in Thesis

All citations appear in **Chapter 3: Theoretical Foundations** ([../supplementary/kapitoly/3_Teoreticka vychodiska.tex](../supplementary/kapitoly/3_Teoreticka vychodiska.tex)), organized by sections:

#### Section 3.1: Decision-Making Under Uncertainty
- **Primary**: Vrana2021, Klir1995, Prokopova2023
- **Context**: Expert decision-making, multiperson decision-making, handling polarized opinions
- **Key concept**: Finding best compromise vs. simple averaging

#### Section 3.2: Fuzzy Set Theory
- **Primary**: Zadeh1965, Klir1995
- **Context**: Vagueness in human judgment, membership functions, fuzzy numbers
- **Key concept**: Paradigm shift from crisp to fuzzy sets, linguistic variables

#### Section 3.3: Object-Oriented Software Development
- **Primary**: Lott2021, Merunka2005
- **Context**: OOP principles (encapsulation, inheritance, polymorphism)
- **Key concept**: Bridging semantic gap, Python as multi-paradigm language
- **Implementation examples**: `FuzzyTriangleNumber` class, UML diagrams

#### Section 3.4: Modern Web Application Architecture
- **Subsection 3.4.1**: Newman2021 (microservices)
- **Subsection 3.4.2**: Fielding2000 (REST API)
- **Subsection 3.4.3**: Kane2018 (Docker containerization)
- **Context**: Independent deployability, stateless communication, consistent deployment

#### Section 3.5: BeCoMe Method
- **Primary**: Vrana2021, Prokopova2023
- **Supporting**: Bellman1970 (contrasted with BeCoMe), Subrt2011 (multi-criteria context)
- **Context**: Mathematical formulation, algorithm steps, practical applications, argument strength

#### Section 3.6: Implementation Rationale
- **Primary**: Vrana2021 (Excel reference implementation)
- **Context**: Limitations of Excel implementation, motivation for Python implementation

---

## Key Concepts and Page References

### Theoretical Foundations

| Concept | Primary Source | Supporting Sources |
|---------|---------------|-------------------|
| Fuzzy triangular numbers | Vrana2021, Klir1995 | Zadeh1965 |
| Arithmetic mean (Γ) | Vrana2021 | - |
| Statistical median (Ω) | Vrana2021 | - |
| Centroid-based sorting | Vrana2021 | - |
| Best compromise (ΓΩMean) | Vrana2021 | - |
| Maximum error (Δmax) | Vrana2021 | - |
| Membership functions | Zadeh1965, Klir1995 | - |
| Decision-making under uncertainty | Bellman1970, Subrt2011 | Vrana2021 |

### Software Engineering

| Concept | Primary Source | Figure Reference |
|---------|---------------|------------------|
| OOP principles | Lott2021, Merunka2005 | Figure 1.5 |
| UML class diagrams | Merunka2005, Lott2021 | Figure 1.5 |
| Microservices | Newman2021 | Figures 1.3, 1.4 |
| REST API | Fielding2000 | Figure 5.10 |
| Docker containers | Kane2018 | Figure 2.3 |

---

## Related Documentation

### Project Documentation

- **Main README**: [../README.md](../README.md) - Project overview
- **Method description**: [method-description.md](method-description.md) - Mathematical formulas (implements Vrana2021)
- **Architecture**: [architecture.md](architecture.md) - Design patterns (implements Newman2021, Lott2021)
- **API reference**: [api-reference.md](api-reference.md) - Implementation details
- **UML diagrams**: [uml-diagrams.md](uml-diagrams.md) - Visual architecture (follows Merunka2005)

### Data and Examples

- **Case studies**: [../examples/data/](../examples/data/) - Budget, Floods, Pendlers datasets (based on Vrana2021 case studies)
- **Analysis scripts**: [../examples/README.md](../examples/README.md) - Implementation examples

### LaTeX Thesis Chapters

- **Chapter 2**: [../supplementary/kapitoly/2_Cil prace & metodika.tex](../supplementary/kapitoly/2_Cil prace & metodika.tex) - Goals and methodology
- **Chapter 3**: [../supplementary/kapitoly/3_Teoreticka vychodiska.tex](../supplementary/kapitoly/3_Teoreticka vychodiska.tex) - Theoretical foundations (all citations)

---

## Digital Object Identifiers (DOIs)

For direct access to peer-reviewed sources:

| Reference | DOI Link |
|-----------|----------|
| Vrana2021 | [10.1016/j.envsoft.2020.104953](https://doi.org/10.1016/j.envsoft.2020.104953) |
| Zadeh1965 | [10.1016/S0019-9958(65)90241-X](https://doi.org/10.1016/S0019-9958(65)90241-X) |
| Bellman1970 | [10.1287/mnsc.17.4.B141](https://doi.org/10.1287/mnsc.17.4.B141) |

---

## Academic Context

All references in this bibliography are cited in the bachelor thesis:

**Thesis Information:**
- **Title**: BeCoMe Method Implementation
- **Author**: Ekaterina Kuzmina
- **University**: Czech University of Life Sciences Prague
- **Faculty**: Faculty of Economics and Management (Provozně ekonomická fakulta)
- **Supervisor**: doc. Ing. Jan Tyrychtr, Ph.D.
- **Academic Year**: 2025/2026
- **Email**: xkuze010@studenti.czu.cz

The bibliography demonstrates:
- Solid theoretical foundation in fuzzy logic and decision theory
- Modern software engineering practices
- Connection to institutional research (Vrana2021, Merunka2005 from CZU)
- Mix of foundational theory (Zadeh1965) and current practices (Newman2021, Lott2021)

---

## Citation Format

### In LaTeX Thesis

Citations use the `biblatex` package with the following commands:

- `\textcite{Vrana2021}` - Textual citation: "Vrana et al. (2021)"
- `\autocite{Vrana2021}` - Parenthetical citation: "(Vrana et al., 2021)"
- `in \textcite{Prokopova2023}` - Secondary source: "in Prokopová (2023)"

### In Academic Papers

For citing this implementation project:

```
Kuzmina, E. (2025-2026). BeCoMe Method Implementation
[Bachelor thesis]. Czech University of Life Sciences Prague,
Faculty of Economics and Management.
```

### For Citing the BeCoMe Method

Always cite the original paper:

```
Vrana, I., Tyrychtr, J., & Pelikán, M. (2021). BeCoMe: Easy-to-implement
optimized method for best-compromise group decision making: Flood-prevention
and COVID-19 case studies. Environmental Modelling & Software, 136, 104953.
https://doi.org/10.1016/j.envsoft.2020.104953
```

---

## Notes

### Research Integrity

- All 11 references are properly cited in thesis chapter 3
- BibTeX file maintained for reproducibility
- No plagiarism or uncited sources
- Proper attribution of figures (Klir1995, Lott2021, Newman2021, Fielding2000, Kane2018, Vrana2021)
- Secondary sources clearly marked (Tyrychtr in Prokopova2023, Brožová in Subrt2011)

### Language Distribution

- **English**: 9 sources (all international publications)
- **Czech**: 2 sources (Subrt2011, Merunka2005) - both relevant to Czech academic context

### Temporal Coverage

- **Historical foundations** (1960s-1970s): Zadeh1965, Bellman1970 - fuzzy logic origins
- **Classical textbooks** (1990s-2000s): Klir1995, Fielding2000, Merunka2005 - established theory
- **Modern practices** (2010s-2020s): All software engineering books - current standards
- **Current research** (2020s): Vrana2021, Prokopova2023 - BeCoMe method

### Open Access

- **Freely available**: Fielding2000 (dissertation), Prokopova2023 (online article)
- **Library access required**: Journal articles (Vrana2021, Zadeh1965, Bellman1970), commercial books
- **Institutional access**: Czech books (Subrt2011, Merunka2005) available at CZU library

---

## Maintenance

This bibliography is synchronized with:

- **LaTeX BibTeX file**: [../supplementary/kapitoly/literatura.bib](../supplementary/kapitoly/literatura.bib)
- **Thesis chapters**: All citations in Chapter 3 ([../supplementary/kapitoly/3_Teoreticka vychodiska.tex](../supplementary/kapitoly/3_Teoreticka vychodiska.tex))

**Last updated**: 2025-11-22

**Update frequency**: Bibliography is stable (thesis submission version). Update only if:
- New references added to thesis
- DOI links change
- Additional implementations cite this work

---

## Contact

For questions about the bibliography or thesis references:

- **Author**: Ekaterina Kuzmina
- **Email**: xkuze010@studenti.czu.cz
- **University**: Czech University of Life Sciences Prague
- **Supervisor**: doc. Ing. Jan Tyrychtr, Ph.D.
