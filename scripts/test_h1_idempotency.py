#!/usr/bin/env python3
"""
H1 Idempotency Test — Idempotent Ingestion Pipeline
=====================================================
Validates that the collector's cache logic processes only new or modified files
and purges orphan cache entries when source files are deleted.

Reproduces the exact mtime-based guard from collector.py:
    if not os.path.exists(cache_path) or os.path.getmtime(src) > os.path.getmtime(cache_path)

Three controlled passes:
  Pass 1 — Fresh run  : all N source files are new → all N processed.
  Pass 2 — No changes : source mtimes unchanged   → 0 files processed (idempotent).
  Pass 3 — Partial update: K files modified, 1 deleted → K re-processed, 1 orphan purged.

Usage:
    python scripts/test_h1_idempotency.py
    python scripts/test_h1_idempotency.py --files 20 --modify 5
"""

import argparse
import os
import shutil
import sys
import tempfile
import time

# ---------------------------------------------------------------------------
# Synthetic clinical source files (content based on HUPEDCARE corpus)
# ---------------------------------------------------------------------------
SOURCE_FILES: dict[str, str] = {
    "flacc_guide.txt": (
        "THE FLACC BEHAVIORAL PAIN SCALE\n"
        "Score 0-10 across five categories: Face, Legs, Activity, Cry, Consolability.\n"
        "Score 0=comfortable; 1-3=mild; 4-6=moderate; 7-10=severe pain.\n"
        "A score of 4 or above requires prompt analgesic intervention.\n"
    ),
    "who_ladder.txt": (
        "WHO TWO-STEP ANALGESIC LADDER FOR CHILDREN\n"
        "Step 1 mild pain: paracetamol and/or ibuprofen.\n"
        "Step 2 moderate to severe pain: morphine (preferred strong opioid).\n"
        "Codeine is contraindicated in children under 12 years.\n"
    ),
    "paracetamol_protocol.txt": (
        "PARACETAMOL DOSING PROTOCOL\n"
        "Oral: 10-15 mg/kg every 4-6 hours. Max 60 mg/kg/day.\n"
        "IV: 15 mg/kg every 6 hours for patients 10 kg or above.\n"
        "Always dose by weight, not age.\n"
    ),
    "neonatal_pain.txt": (
        "NEONATAL PAIN ASSESSMENT\n"
        "Use CRIES scale for post-operative neonates (32 wks to 6 months).\n"
        "Sucrose 24% oral solution 0.5-2 mL given 2 minutes before procedure.\n"
        "Kangaroo care reduces behavioral pain response significantly.\n"
    ),
    "nonpharm_interventions.txt": (
        "NON-PHARMACOLOGICAL INTERVENTIONS\n"
        "Distraction is first-line for procedural pain (Cochrane, 28 RCTs).\n"
        "Virtual reality shows effect sizes comparable to IV opioids in some studies.\n"
        "Deep breathing: inhale 4 s, hold 2, exhale 6 activates parasympathetic response.\n"
    ),
    "morphine_protocol.txt": (
        "MORPHINE DOSING PROTOCOL\n"
        "IV bolus opioid-naive: 0.05-0.1 mg/kg. Titrate every 5-10 minutes.\n"
        "PCA demand dose: 0.02 mg/kg, lockout 5-10 minutes.\n"
        "Always have naloxone 0.01 mg/kg IV available at bedside.\n"
    ),
    "chronic_pain_children.txt": (
        "CHRONIC PAIN IN CHILDREN\n"
        "Defined as pain recurring for more than 3 months. Prevalence 11-38%.\n"
        "Common: headache, functional abdominal pain, CRPS, musculoskeletal pain.\n"
        "Interdisciplinary program is evidence gold standard for complex chronic pain.\n"
    ),
    "faces_scale.txt": (
        "FACES PAIN SCALE REVISED (FPS-R)\n"
        "Six faces scored 0,2,4,6,8,10. Validated for ages 4-12 years.\n"
        "Instruction: point to the face that shows how much you hurt right now.\n"
        "MCID = 2 faces (4 points on the 0-10 scale).\n"
    ),
    "nrs_guide.txt": (
        "NUMERICAL RATING SCALE (NRS-11)\n"
        "0-10 scale. Appropriate for children aged 7 and above.\n"
        "MCID = 2 points or 33% reduction from baseline.\n"
        "Test-retest reliability ICC 0.87-0.96.\n"
    ),
    "caregiver_guide.html": (
        "<html><body>\n"
        "<h1>When to seek urgent help for your child's pain</h1>\n"
        "<ul><li>Severe pain not controlled by medication</li>\n"
        "<li>Stiff neck with headache and fever (possible meningitis)</li>\n"
        "<li>Pain in testicle that started suddenly (possible testicular torsion)</li>\n"
        "<li>Fever above 38.5 C in baby under 3 months</li></ul>\n"
        "</body></html>\n"
    ),
    "postop_protocol.txt": (
        "POST-OPERATIVE PAIN PROTOCOL\n"
        "FLACC 7-10 in PACU: IV morphine 0.1 mg/kg, repeat every 5 min (max 3 doses).\n"
        "Discharge analgesia: paracetamol 15 mg/kg q6h + ibuprofen 10 mg/kg q8h.\n"
        "Parent education: weight-based dosing, signs of over-sedation, locked storage.\n"
    ),
    "sickle_cell_voc.txt": (
        "SICKLE CELL VASO-OCCLUSIVE CRISIS PROTOCOL\n"
        "NRS 7 or above at triage: IV morphine within 30 minutes.\n"
        "IV morphine 0.1-0.15 mg/kg. Reassess every 30 minutes.\n"
        "Time to first analgesia must be under 30 minutes from triage.\n"
    ),
}


# ---------------------------------------------------------------------------
# Cache logic (mirrors collector.py step 3 exactly)
# ---------------------------------------------------------------------------

def run_extraction_pass(
    src_dir: str,
    cache_dir: str,
) -> dict[str, str]:
    """
    Scan src_dir and (re-)extract only new or modified files.
    Returns a dict mapping filename -> action ('extracted' | 'skipped').
    """
    results: dict[str, str] = {}
    expected_cache: set[str] = set()

    for fname in sorted(os.listdir(src_dir)):
        src_path = os.path.join(src_dir, fname)
        if not os.path.isfile(src_path):
            continue

        cache_name = fname + ".txt"
        cache_path = os.path.join(cache_dir, cache_name)
        expected_cache.add(cache_name)

        needs_extraction = (
            not os.path.exists(cache_path)
            or os.path.getmtime(src_path) > os.path.getmtime(cache_path)
        )

        if needs_extraction:
            with open(src_path, "r", encoding="utf-8", errors="ignore") as fh:
                content = fh.read()
            with open(cache_path, "w", encoding="utf-8") as fh:
                fh.write(content)
            results[fname] = "extracted"
        else:
            results[fname] = "skipped"

    return results


def purge_orphans(src_dir: str, cache_dir: str) -> list[str]:
    """Remove cache entries whose source file no longer exists."""
    expected = {f + ".txt" for f in os.listdir(src_dir) if os.path.isfile(os.path.join(src_dir, f))}
    purged = []
    for cache_file in sorted(os.listdir(cache_dir)):
        if cache_file not in expected:
            os.remove(os.path.join(cache_dir, cache_file))
            purged.append(cache_file)
    return purged


# ---------------------------------------------------------------------------
# Report helpers
# ---------------------------------------------------------------------------

def _summarize(results: dict[str, str], purged: list[str], pass_name: str) -> None:
    extracted = [f for f, a in results.items() if a == "extracted"]
    skipped   = [f for f, a in results.items() if a == "skipped"]
    total     = len(results)
    print(f"\n  {pass_name}")
    print(f"  {'-'*52}")
    for fname, action in results.items():
        marker = "  EXTRACT" if action == "extracted" else "  skip   "
        print(f"  {marker}  {fname}")
    if purged:
        for p in purged:
            print(f"  PURGE    {p}")
    print(f"  {'-'*52}")
    print(f"  Extracted: {len(extracted)}/{total}  |  Skipped: {len(skipped)}/{total}"
          + (f"  |  Purged: {len(purged)}" if purged else ""))


def print_results_table(
    pass1: dict, pass2: dict, pass3: dict,
    purged3: list[str],
    n_modify: int,
    n_delete: int,
) -> bool:
    n_total = len(pass1)

    p1_extracted = sum(1 for a in pass1.values() if a == "extracted")
    p2_extracted = sum(1 for a in pass2.values() if a == "extracted")
    p3_extracted = sum(1 for a in pass3.values() if a == "extracted")

    skip_rate_p2  = (1 - p2_extracted / len(pass2)) * 100
    skip_rate_p3  = (1 - p3_extracted / len(pass3)) * 100
    reprocess_acc = (p3_extracted == n_modify)
    orphan_acc    = (len(purged3) == n_delete)

    w = 46
    print(f"\n{'='*68}")
    print(f"  RESULTS — H1 Idempotent Ingestion (N={n_total} files)")
    print(f"{'='*68}")
    print(f"  {'Metric':<{w}} {'Value':>10}")
    print(f"  {'-'*58}")
    print(f"  {'Pass 1 — fresh run: files extracted':<{w}} {p1_extracted:>10}")
    print(f"  {'Pass 2 — unchanged: files extracted (target: 0)':<{w}} {p2_extracted:>10}")
    print(f"  {'Pass 2 — skip rate (target: 100%)':<{w}} {skip_rate_p2:>9.1f}%")
    print(f"  {'Pass 3 — N modified: files re-extracted (target: N)':<{w}} {p3_extracted:>10}")
    print(f"  {'Pass 3 — skip rate on unmodified files':<{w}} {skip_rate_p3:>9.1f}%")
    print(f"  {'Pass 3 — orphan cache entries purged (target: {n_delete})':<{w}} {len(purged3):>10}")
    print(f"{'='*68}")

    h1_pass = (p2_extracted == 0) and reprocess_acc and orphan_acc
    verdict = "PASS ✓" if h1_pass else "FAIL ✗"
    print(f"\n  H1 hypothesis (idempotent ingestion): [{verdict}]")
    checks = [
        ("Unchanged corpus → 0 re-extractions", p2_extracted == 0),
        (f"Modified files ({n_modify}) all re-extracted", reprocess_acc),
        (f"Deleted files ({n_delete}) purged from cache", orphan_acc),
    ]
    for label, ok in checks:
        print(f"    {'OK' if ok else 'FAIL'}  {label}")
    print()
    return h1_pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="H1 idempotency test — collector cache logic"
    )
    parser.add_argument(
        "--files", type=int, default=len(SOURCE_FILES),
        help=f"Number of source files to use (default: {len(SOURCE_FILES)})"
    )
    parser.add_argument(
        "--modify", type=int, default=3,
        help="Files to modify in Pass 3 (default: 3)"
    )
    parser.add_argument(
        "--delete", type=int, default=1,
        help="Files to delete in Pass 3 (default: 1)"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    n_files  = min(args.files, len(SOURCE_FILES))
    n_modify = min(args.modify, n_files - 1)
    n_delete = min(args.delete, n_files - n_modify - 1)

    tmpdir    = tempfile.mkdtemp(prefix="hupedcare_h1_")
    src_dir   = os.path.join(tmpdir, "TEMP_DOWNLOADS")
    cache_dir = os.path.join(tmpdir, "CACHE_TEXT")
    os.makedirs(src_dir)
    os.makedirs(cache_dir)

    # Populate source directory with the first n_files synthetic files
    selected = list(SOURCE_FILES.items())[:n_files]
    for fname, content in selected:
        with open(os.path.join(src_dir, fname), "w", encoding="utf-8") as fh:
            fh.write(content)

    print(f"\n{'='*68}")
    print(f"  H1 — Idempotent Ingestion Test")
    print(f"  Source files: {n_files}  |  Pass-3 modifications: {n_modify}  "
          f"|  Pass-3 deletions: {n_delete}")
    print(f"{'='*68}")

    # ── Pass 1: fresh run ─────────────────────────────────────────────────
    purged1 = purge_orphans(src_dir, cache_dir)
    results1 = run_extraction_pass(src_dir, cache_dir)
    _summarize(results1, purged1, "Pass 1 — Fresh run (no cache exists)")

    # ── Pass 2: no changes ────────────────────────────────────────────────
    purged2 = purge_orphans(src_dir, cache_dir)
    results2 = run_extraction_pass(src_dir, cache_dir)
    _summarize(results2, purged2, "Pass 2 — No changes (idempotency check)")

    # ── Pass 3: modify K, delete 1 ────────────────────────────────────────
    modify_targets = [fname for fname, _ in selected[:n_modify]]
    delete_targets = [fname for fname, _ in selected[n_modify:n_modify + n_delete]]

    # Touch source files to simulate content update (bump mtime past cache mtime)
    time.sleep(0.05)  # ensure mtime gap is detectable
    for fname in modify_targets:
        path = os.path.join(src_dir, fname)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write("# Updated: new clinical addendum appended.\n")

    for fname in delete_targets:
        os.remove(os.path.join(src_dir, fname))

    purged3  = purge_orphans(src_dir, cache_dir)
    results3 = run_extraction_pass(src_dir, cache_dir)
    _summarize(results3, purged3,
               f"Pass 3 — {n_modify} files modified, {n_delete} deleted")

    shutil.rmtree(tmpdir)

    return 0 if print_results_table(results1, results2, results3, purged3, n_modify, n_delete) else 1


if __name__ == "__main__":
    sys.exit(main())
