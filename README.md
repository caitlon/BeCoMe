# BeCoMe

Software that helps a panel of experts turn genuine disagreement into one defensible number.

**Live: [becomify.app](https://www.becomify.app)**

![Python](https://img.shields.io/badge/python-3.13+-blue.svg)
![TypeScript](https://img.shields.io/badge/typescript-5.0+-blue.svg)
![FastAPI](https://img.shields.io/badge/fastapi-0.115+-green.svg)
![React](https://img.shields.io/badge/react-18+-blue.svg)
![Tests](https://img.shields.io/badge/tests-2823%20passed-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-99%25-brightgreen)

## Contents

- [The problem](#the-problem)
- [How BeCoMe answers it](#how-become-answers-it)
- [Three real cases](#three-real-cases)
- [Try it](#try-it)
- [Where the method comes from](#where-the-method-comes-from)
- [Project status](#project-status)
- [For developers](#for-developers)
- [License and contact](#license-and-contact)
- [References](#references)

## The problem

Ask thirteen experts how much arable land a country should convert into flood plains and you get thirteen different answers, most of them ranges rather than single numbers. The hydrologists on one Czech panel recommended converting 37 to 47 percent. The land owners, whose fields those would be, said 0 to 4. Both groups had good reasons.

The usual move is to average everything, and it fails quietly here. The plain average of that panel is about 20 percent, a figure not one of the thirteen would defend: far too little for the hydrologists, ruinous for the farmers. It is also fragile. Add one more strong opinion at either end and the answer moves again.

## How BeCoMe answers it

Each expert gives three numbers instead of one: the lowest value they would accept, the value they consider most likely, and the highest. That is a fuzzy triangular number, and it lets someone say "around 40, but I could live with 37" without claiming a precision they do not have.

The method then computes two things the panel already implies. The average shows where the opinions sit in aggregate. The median shows where the middle of the panel sits, and it barely moves when one person takes an extreme position. BeCoMe combines the two into a best compromise, and it reports the distance between them as a number in its own right.

That second number is the useful part. On the flood panel the average landed at 20.3 percent and the median at 8.3, so the compromise came out at 14.3, with a disagreement measure of 5.97. A panel that genuinely agrees produces a small one: the COVID-19 budget panel of 22 officials scored 2.20. The method does not hide a split under a single confident-looking figure. It tells you the split is there.

## Three real cases

The project ships the three panels the method's authors published, with the original data.

**Flood prevention.** 13 experts, split between hydrologists, land owners, rescue coordinators, and economists, on how much arable land to convert. The most polarized of the three, and the reason outlier resistance matters.

**COVID-19 budget support.** 22 Czech officials, among them deputy ministers, the Police President, and the Chief Hygienist, estimating support for affected businesses in billions of CZK. This panel largely agreed, and the numbers show it.

**Cross-border travel.** 22 public health and border officials rating pandemic travel policy on a five-point scale. It shows the method handling ordinary survey answers as well as ranges.

Every result matches the authors' own Excel workbook to within 0.001, and CI re-checks that on every commit.

## Try it

Open [becomify.app](https://www.becomify.app), register, create a project, invite experts, and collect opinions. Nothing to install.

To run one of the published cases from a terminal instead:

```bash
uv sync --extra dev
uv run python -m examples.analyze_budget_case
```

## Where the method comes from

I. Vrana, J. Tyrychtr, and M. Pelikán, of the Faculty of Economics and Management at the Czech University of Life Sciences Prague, published BeCoMe in *Environmental Modelling & Software*. Ekaterina Kuzmina wrote this independent implementation of that paper at the same faculty. A web application wraps it, so that people who do not write code can run a panel.

The [method description](docs/method-description.md) works through the mathematics step by step, with the formulas and a complete example.

## Project status

This is an MVP: a working proof of concept rather than a finished product. The three published case studies run end to end, the web application is live, and the results match the reference implementation. It is under active development and the scope is still growing.

## For developers

| Document | What it covers |
|----------|----------------|
| [Development setup](docs/development.md) | Requirements, install, dependency groups, project structure |
| [Method description](docs/method-description.md) | The mathematics, with worked examples |
| [Core library](src/README.md) | Models, calculators, interpreters, design patterns |
| [REST API](api/README.md) | Endpoints, auth flow, configuration, observability |
| [Frontend](frontend/README.md) | React app, environment variables, Docker |
| [Environments](docs/environments.md) | The dev, test, and prod profiles, and Railway deployment |
| [Security](docs/security.md) | Authentication, tenant isolation, GDPR, database posture |
| [Quality report](docs/quality-report.md) | Coverage, mutation testing, performance |
| [Tests](tests/README.md) | Suite layout and how to run it |
| [Examples](examples/README.md) | The three case studies and custom data |
| [UML diagrams](docs/uml-diagrams/README.md) | Class, sequence, and activity diagrams |

The stack is FastAPI and SQLModel on the backend, React with TypeScript and Tailwind on the frontend, PostgreSQL in the deployed environments and SQLite locally. mypy runs in strict mode, and the core library sits at 100% test coverage.

## License and contact

**Academic use**: this code serves academic and research purposes. If you build on this implementation, cite the original BeCoMe paper by Vrana et al. (2021), listed under [References](#references).

**Copyright**: © 2025-2026 Ekaterina Kuzmina

**Contact**: Ekaterina Kuzmina, xkuze010@studenti.czu.cz, Czech University of Life Sciences Prague.

## References

Vrana, I., Tyrychtr, J., & Pelikán, M. (2021). BeCoMe: Easy-to-implement optimized method for best-compromise group decision making: Flood-prevention and COVID-19 case studies. *Environmental Modelling & Software*, 136, 104953. https://doi.org/10.1016/j.envsoft.2020.104953

Foundational background: fuzzy logic (Zadeh 1965, and Bellman & Zadeh 1970).

All case study data is in `examples/data/`, with format specifications and provenance in [examples/data/README.md](examples/data/README.md).

Thanks to the method's authors.

A longer write-up of this implementation is in [thesis/main.pdf](thesis/main.pdf).
