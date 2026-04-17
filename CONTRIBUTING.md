# Contributing Guide

Thanks for contributing to the HUPEDCARE chatbot project.

## Development Setup

1. Create and activate a virtual environment.
2. Install runtime dependencies:

```bash
pip install -r requirements.txt
```

## Branch and Commit Recommendations

- Use short topic branches (for example `feat/retrieval-metrics` or `fix/sql-timeout`).
- Prefer focused commits with clear messages.
- Keep each change scoped to one logical objective.

## Change Checklist

- [ ] The API starts locally (`python src/server.py`).
- [ ] The ingestion pipeline runs locally (`python src/collector.py`).
- [ ] Documentation is updated when behavior changes.
- [ ] Config changes are reflected in `README.md`.

## Reporting Bugs

Please include:

- Expected behavior
- Actual behavior
- Reproduction steps
- Logs or stack traces (with secrets removed)
