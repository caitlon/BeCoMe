# BeCoMe review rules

Greptile is a semantic reviewer for this repository. These rules describe judgment-based
standards that a linter cannot enforce. Structured, file-scoped rules live in `config.json`.
The guidelines below apply repository-wide and benefit from explanation.

## Scope of review

Focus on architecture, correctness, and contract violations. Leave formatting, import
sorting, and pure style to the existing tools: Ruff (`E, W, F, I, N, UP, B, SIM, RUF`) and
mypy strict on Python, ESLint on the frontend. Do not duplicate what those tools already
report.

## Clean refactoring: delete, never park

When you remove or refactor functionality, delete it completely. Git history is the record
of what used to exist, so leftovers do not belong in the working tree. Flag any of these:

- commented-out blocks kept "for reference"
- `_old` or `_deprecated` suffixes, and parallel "v2" copies
- backward-compatibility shims or fallbacks for code that no longer exists
- `# TODO: remove later` notes, where the removal can happen now instead

A refactor is incomplete until you update every test and call site that referenced the old
code.

```python
# Bad -- dead code left behind
# def old_centroid(self): ...
def centroid(self): ...
```

## No magic numbers in calculators

Numeric constants inside the aggregation math must carry a domain name, either as a class
attribute or as an explicit parameter. That keeps each formula verifiable against the
documented BeCoMe method. A bare literal in the middle of a calculation hides intent and
blocks parametrization.

```python
# Bad
result = total / 2

# Good
HALVES = 2  # GammaOmega mean averages the arithmetic mean and the median
result = total / HALVES
```

## Test clarity

Every test reads as GIVEN (setup) -> WHEN (the action under test) -> THEN (assertions). The
test name describes the behavior it verifies. Each test keeps a single logical focus instead
of asserting several unrelated things at once. Unclear structure makes a failure hard to
diagnose.

## Comments explain "why", not "what"

Prefer self-documenting names over comments. When a comment earns its place, it explains a
non-obvious decision or trade-off, not a restatement of the code. Docstrings are the public
contract of an object (see the `py-docstring-contracts` rule). Inline comments are notes for
maintainers.
