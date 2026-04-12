# Project Backlog

This file tracks shared project work across software, integration, experiments, and manuscript preparation.

## Status Legend

- `todo`: not started
- `in-progress`: currently being worked on
- `blocked`: waiting on an external dependency or decision
- `done`: completed

## Current Priorities

| ID | Area | Task | Status | Priority | Notes |
| --- | --- | --- | --- | --- | --- |
| B1 | Collector | Configure the collector for the HUPEDCARE deployment context | `todo` | high | Review config sources, credentials flow, storage paths, and expected data sources. |
| B2 | Collector | Run the collector on a fixed schedule | `todo` | high | Decide between OS scheduler, container scheduler, or process supervisor. |
| B3 | Client | Prepare embeddable PHP integration code for connecting to the server | `todo` | medium | Define integration contract, endpoint URL handling, and host-page requirements. |
| B4 | GitHub | Prepare the project documentation and repository presentation in GitHub | `todo` | medium | README polish, contribution guidance, release notes, and documentation structure. |
| A1 | Manuscript | Draft the scientific paper based on the implemented system and experiments | `in-progress` | high | Main LaTeX manuscript already exists in `docs/main.tex`. |
| A2 | Experiments | Run the planned experiments and populate result tables | `todo` | high | Required to replace placeholders in the Results section. |
| A3 | Venue | Select a target journal or conference and adapt the manuscript accordingly | `todo` | medium | Align formatting, framing, and contribution emphasis with the target venue. |

## Suggested Milestones

### M1. Deployment Readiness

- Configure the collector for HUPEDCARE.
- Define and implement scheduled execution.
- Validate end-to-end ingestion and refresh flow.

### M2. Integration Readiness

- Prepare PHP embedding or integration code.
- Confirm server endpoint contract and deployment URL strategy.
- Document integration steps for external websites.

### M3. Project Packaging

- Improve GitHub-facing documentation.
- Review repository structure and onboarding notes.
- Prepare the repository for external review.

### M4. Paper Submission Readiness

- Complete the manuscript draft.
- Execute the evaluation protocol and fill result tables.
- Add statistical and error analysis.
- Choose target venue and adapt formatting if needed.