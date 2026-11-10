# Open-access test corpus for the HUPEDCARE attribution evaluation

**These documents are published literature used as test material. They were not curated or reviewed for clinical use. This corpus is not clinical guidance.**

| File | Contents |
|---|---|
| `selection.csv` | Every candidate, with the decision and the reason for each exclusion |
| `corpus.txt` | Text of the included documents, with one source header per document |
| `ATTRIBUTION.csv` | Source, authors, journal, year, DOI, licence and adaptation of each document |
| `search/` | PubMed Central search of 2026-11-09 (query in `survey_pmc.py`) and screening scripts |
| `questions.json` | The 418 answerable and 185 near-miss questions, with the translations |
| `PREREGISTRATION.md` | Analysis plan, with its amendments |

111 articles are licensed CC BY (verified in each article's metadata). Text was extracted and split into passages, and tables, figures and reference lists were removed.

The WHO guideline is licensed CC BY-NC-SA 3.0 IGO, which differs from the other documents: it may not be used commercially, and adaptations must keep the same licence.
