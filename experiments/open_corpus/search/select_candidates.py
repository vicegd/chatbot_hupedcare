#!/usr/bin/env python3
"""
Second screening step of the corpus search: from the articles that passed survey_pmc.py to the
proposed list. Reads pmc_candidates.csv and writes pmc_proposed.csv. No network access.

Usage:
    python -I select_candidates.py pmc_candidates.csv pmc_proposed.csv
"""

import csv
import re
import sys

GUIDELINE = re.compile(r"guideline|recommendation|consensus", re.I)
OFF_TOPIC = re.compile(r"cost|economic|bupivacaine versus|mediation analysis|digital health implementation|app:|qualitative", re.I)
FIELDS = ["pmcid", "doi", "year", "kind", "words", "journal", "topics", "license", "title"]


def keep(row):
    if row["journal"] == "Cureus" or OFF_TOPIC.search(row["title"]) or not row["topics"]:
        return False
    if int(row["year"] or 0) < 2018 or int(row["words"]) > 20000:
        return False
    return row["kind"] in ("review-article", "systematic-review") or bool(GUIDELINE.search(row["title"]))


with open(sys.argv[1], encoding="utf-8") as handle:
    selected = [r for r in csv.DictReader(handle) if r["status"] == "ok" and keep(r)]
selected.sort(key=lambda r: (r["topics"].split(";")[0], -int(r["year"])))
with open(sys.argv[2], "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=FIELDS)
    writer.writeheader()
    for row in selected:
        writer.writerow({k: row[k] for k in FIELDS})
print(len(selected))
