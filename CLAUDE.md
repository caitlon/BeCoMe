# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## MCP Tools Usage

**Always use MCP tools proactively without being asked:**

- **context7**: Use automatically when code generation, setup/configuration steps, or library/API documentation is needed. Resolve library IDs and fetch docs without explicit user request.
- **sequential-thinking**: Use for breaking down complex problems or planning multi-step implementations.
- **ide**: Check diagnostics periodically when working with code to catch errors early.

## Git Workflow

- **After making changes, always suggest a commit message** in English using conventional commits format
- Format: `<type>: <short description>` (e.g., `feat: add kennard-stone splitting`, `fix: correct preprocessing pipeline`, `chore: update dependencies`)
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- Keep it concise (max 50 characters)

## Viewing Notebook Images

To view plots/images from Jupyter notebooks, extract them from the .ipynb file and read as PNG:

```bash
# Extract image from cell N (0-indexed) and save to temp file
cat <notebook_path> | jq -r '.cells[N].outputs[0].data["image/png"]' | base64 -d > /tmp/plot.png

# Then read the image with Read tool
```

Use this when analyzing EDA notebooks in `notebooks/` directory. The cell index can be found by reading the notebook first — look for cells with "Outputs are too large to include" message.

## Writing Style for Comments, Documentation, and README

**CRITICAL: Always follow the writing guidelines in `/ek/md/rules.md`** when writing:
- Code comments and docstrings
- README files and documentation
- Commit messages (longer descriptions)
- Any user-facing text or explanations

**Key principles from rules.md:**
1. **Vary sentence length** - mix short, medium, and long sentences (burstiness)
2. **Avoid AI patterns** - no "not X, but Y", no "it's important to note", no "moreover/furthermore"
3. **Natural transitions** - don't start every sentence with formal connectors
4. **Personal voice** - use specific examples, show personality, avoid generic statements
5. **No template structures** - break symmetry, vary paragraph lengths
6. **Minimal bullet points** - prefer narrative text over lists in documentation

**Never use these phrases:**
- "It's not just X, it's Y"
- "Moreover", "Furthermore", "Additionally" (at every turn)
- "In today's world", "In the realm of"
- "It's important to note that"
- "Delve", "navigate", "landscape" (as metaphors)

**Instead:**
- Write directly and specifically
- Use concrete examples from the codebase
- Vary structures naturally
- Sound like you're explaining to a colleague, not reciting a template

## Project Overview

NIR (Near-Infrared) spectroscopy analysis for cacao bean quality prediction. The codebase has two independent ML pipelines:
- **Classification**: Predict bean quality categories (OK, Mouldy, Insect, etc.)
- **Regression**: Predict continuous values (Brix, pH, Fat, Moisture)

## Commands

### Running Experiments

```bash
# Classification pipeline
python -m src.classification.main
python -m src.classification.main -p snv_mean_agg -m "Random Forest" -c BINARY_CATEGORY
python -m src.classification.main --dry-run  # preview experiments
python -m src.classification.main --list-preproc  # show preprocessing options
python -m src.classification.main --list-models  # show available models
python -m src.classification.main --list-categories  # show category mappings
python -m src.classification.main --split-method SR  # SR=stratified+random, R=random
python -m src.classification.main --measurement-type bean  # bean or combined

# Regression pipeline
python -m src.regression.training.run brix --method optuna
python -m src.regression.training.run fat --method grid --split-method kennard_stone
python -m src.regression.training.run ph --method optuna --measurement-type C  # C, B, or CB
```

### Linting and Testing

```bash
ruff check src/
ruff format src/
pytest tests/
pytest tests/classification/ -v
pytest tests/regression/test_splitting_methods.py::test_kennard_stone_split_when_available -v
```

### Installation

This project uses **uv** as the package manager. Virtual environment is located at `.venv/` in the project root.

```bash
# Sync all dependencies including dev
uv sync --extra dev

# Run scripts within the venv
uv run python -m src.classification.main
uv run pytest tests/
```

Always prefer `uv` commands over standard `pip`.

## Architecture

### Module Structure

```
src/
├── core/                   # Shared utilities used by both pipelines
│   ├── constants.py        # Wavelengths, column names, model params
│   ├── paths.py            # File path management
│   ├── logger.py           # Logging utilities
│   ├── splitting.py        # Train/val/test splitting methods
│   ├── sklearn_pipeline.py # sklearn helpers
│   ├── config/             # Pydantic config classes
│   └── data_processing/
│       ├── cleaning.py      # Column fixing, deduplication
│       ├── preprocessing.py # SNV, MSC, derivatives, Savitzky-Golay
│       ├── aggregation.py   # Mean/median/max aggregation per bean
│       ├── outliers.py      # PCA, zscore, Mahalanobis detection
│       └── measurements.py  # Measurement types (CUT, BEAN)
├── classification/         # Classification pipeline
│   ├── main.py             # CLI entry point
│   ├── config.py           # Pydantic configs, category mappings
│   ├── preprocessing.py    # Data preprocessing
│   ├── splitting.py        # Classification-specific splitting
│   ├── metrics.py          # F1, accuracy, confusion matrix
│   ├── optimization.py     # Hyperparameter optimization
│   ├── reporting.py        # Results reporting
│   ├── models/             # RF, SVM, MLP, PCA-RF, PLS-DA
│   └── orchestrator/       # Multi-run management via subprocesses
└── regression/             # Regression pipeline
    ├── config.py           # Experiment configs (brix, ph, fat, moisture)
    ├── metrics.py          # RMSE, R², RPD, RER, Bias
    ├── training/
    │   ├── run.py          # CLI entry point
    │   ├── base.py         # Data preparation utilities
    │   └── search.py       # Optuna/grid search
    ├── splitting/          # Split methods (stratified, random, kennard_stone)
    ├── preprocessing/      # Data cleaning, target handling
    ├── reporting/          # Results reporting
    └── models/             # 9 sklearn regressors + 1D-CNN
```

### Key Patterns

**Pydantic for configuration**: All experiment configs use Pydantic models (`ExperimentConfig`, `OptimizationConfig`, `PreprocessingConfig`). Find definitions in `src/*/config.py`.

**Category mappings**: Classification uses multiple category groupings defined in `src/classification/config.py`:
- `CATEGORY_CODE` - original 6 classes
- `BINARY_CATEGORY` - OK vs Others
- `OVS_MWI_CATEGORY`, `OVSW_MI_CATEGORY`, `O_VSW_MI_CATEGORY` - various groupings

**Preprocessing pipeline**: Spectral preprocessing methods are registered in `src/core/data_processing/preprocessing.py` with short codes. Available methods:
- Scatter correction: `snv`, `msc`, `rnv`, `emsc`
- Baseline: `detrend`, `arpls`
- Derivatives: `first_derivative`, `second_derivative`, `sgfd`, `sgsd`
- Combinations: `snv_first_derivative`, `snv_second_derivative`, `msc_sgfd`, `dt_snv`, `arpls_snv`

**Splitting strategies**: Both pipelines support multiple split methods - `stratified_bin`, `random`, `kennard_stone` for regression; `SR` (stratified+random), `R` (random) for classification.

**Metrics**: Regression uses RMSE, R², RPD (>3.0 excellent), RER (>20 excellent), and Bias. Classification uses F1 macro, accuracy, and per-class confusion matrix metrics (TP/TN/FP/FN).

### Data Layout

- `data/classification/` - Amsterdam dataset for classification
- `data/regression/` - pH/Brix and Fat/Moisture datasets
- `logs/` - Experiment outputs and saved models

### Additional Directories

- `notebooks/` - EDA and outlier analysis Jupyter notebooks
- `scripts/` - Helper scripts (orchestrator runner)
- `dev/` - Pipeline development and experiments
- `taskfiles/` - Taskfile automation configs (11 files)
- `cacao_mlflow/` - MLflow integration
- `ek/` - Reference materials and scientific papers

## Code Style

- Line length: 100 characters
- Uses ruff for linting/formatting
- ML naming conventions allowed: `X_train`, `y_test`, etc. (N803/N806 ignored)
- `archive_code/` is excluded from linting
- **All code, comments, docstrings, and variable names must be in English**

## Refactoring Guidelines

When removing functionality or refactoring code, delete everything cleanly:
- No commented-out code blocks "for reference"
- No unused imports left behind
- No backward-compatibility shims or fallbacks to old logic
- No "backup" variables or functions with `_old`, `_deprecated` suffixes
- No `# TODO: remove later` comments — remove it now
- Update all tests that reference removed functionality
- If a function/class is deleted, remove it from all imports and usages across the codebase
