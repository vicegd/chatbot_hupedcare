# Contributing Guide

Thanks for contributing to the HUPEDCARE chatbot project.

## Development Setup

1. Create and activate a virtual environment.
2. Install runtime and development dependencies:

```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## Local Quality Checks

Run these checks before opening a pull request:

```bash
ruff check src tests
pytest -q
```

## Branch and Commit Recommendations

- Use short topic branches (for example `feat/retrieval-metrics` or `fix/sql-timeout`).
- Prefer focused commits with clear messages.
- Keep each pull request scoped to one logical change.

## Pull Request Checklist

- [ ] Code builds and tests pass locally.
- [ ] Lint checks pass.
- [ ] Documentation is updated when behavior changes.
- [ ] Config changes are reflected in `README.md`.

## Reporting Bugs

Please use the bug report template and include:

- Expected behavior
- Actual behavior
- Reproduction steps
- Logs or stack traces (with secrets removed)
