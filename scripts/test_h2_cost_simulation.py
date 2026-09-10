#!/usr/bin/env python3
"""
H2 Cost Simulation Test — Hash-Gated Conditional Reindexing
=============================================================
Simulates a 30-day update cycle to compare:
  - Baseline : stateless full reindex on every cycle
  - HUPEDCARE: hash-gated conditional reindexing

Fills in the quantitative values required by Table 5 (Section 5)
of the article, without making any real embedding API calls.

Usage:
    python scripts/test_h2_cost_simulation.py
    python scripts/test_h2_cost_simulation.py --cycles 60 --changes 3,10,20,40,55
"""

import argparse
import hashlib
import os
import shutil
import sys
import tempfile
import time

# ---------------------------------------------------------------------------
# Constants — must match config.yaml and the OpenAI pricing page
# ---------------------------------------------------------------------------
EMBEDDING_MODEL       = "text-embedding-3-small"
PRICE_PER_MILLION_TOKENS = 0.020          # USD per 1M tokens (OpenAI, 2024)
CHARS_PER_TOKEN       = 4.0               # rough approximation for English text
H2_THRESHOLD_PCT      = 85.0              # article hypothesis: ≥85 % cost reduction

# Corpus lives two directories above this script
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CORPUS = os.path.join(_SCRIPT_DIR, "..", "data", "master_context.txt")

# Realistic 30-day change schedule: days when a new document is ingested
DEFAULT_CHANGE_DAYS = [3, 8, 15, 22]     # 4 updates → 86.7 % no-change cycles


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def md5_of_file(path: str) -> str:
    hasher = hashlib.md5()
    with open(path, "rb") as fh:
        hasher.update(fh.read())
    return hasher.hexdigest()


def estimate_tokens(path: str) -> int:
    return int(os.path.getsize(path) / CHARS_PER_TOKEN)


def mock_embed(corpus_path: str) -> tuple[int, float]:
    """
    Simulates the embedding call: counts tokens and measures disk-read latency.
    No network call is made; cost is computed analytically from token count.
    """
    t0 = time.perf_counter()
    tokens = estimate_tokens(corpus_path)
    # Replicate the I/O work the real call would do (read file for chunking)
    with open(corpus_path, "rb") as fh:
        fh.read()
    latency = time.perf_counter() - t0
    return tokens, latency


def apply_corpus_change(corpus_path: str, cycle: int) -> None:
    """Appends a synthetic SOURCE block to simulate a new clinical document."""
    with open(corpus_path, "a", encoding="utf-8") as fh:
        fh.write(
            f"\n--- SOURCE: clinical_update_cycle_{cycle:02d}.pdf ---\n"
            f"New protocol addendum ingested on cycle {cycle}. "
            f"Pediatric pain management update for institutional review.\n"
        )


# ---------------------------------------------------------------------------
# Simulation core
# ---------------------------------------------------------------------------

def run_simulation(corpus_src: str, cycles: int, change_days: list[int]):
    tmpdir = tempfile.mkdtemp(prefix="hupedcare_h2_")
    corpus = os.path.join(tmpdir, "master_context.txt")
    shutil.copy2(corpus_src, corpus)

    initial_tokens  = estimate_tokens(corpus)
    initial_bytes   = os.path.getsize(corpus)

    print(f"\n{'='*68}")
    print(f"  H2 — Hash-Gated Cost Simulation ({cycles} cycles)")
    print(f"  Corpus : {initial_bytes:,} bytes  |  ~{initial_tokens:,} tokens")
    print(f"  Changes: cycles {sorted(change_days)}")
    print(f"{'='*68}\n")
    print(f"  {'Cycle':>5}  {'Baseline':>12}  {'HUPEDCARE':>12}  Note")
    print(f"  {'-'*60}")

    # Pre-initialize hash: system is already deployed before the 30-day window starts.
    # Cycle 1 therefore correctly skips unless the corpus changed since last run.
    stored_hash   = md5_of_file(corpus)
    rows_baseline = []
    rows_hashed   = []

    for cycle in range(1, cycles + 1):
        if cycle in change_days:
            apply_corpus_change(corpus, cycle)

        # ── Baseline: always reindex ───────────────────────────────────
        t0 = time.perf_counter()
        tokens_b, _  = mock_embed(corpus)
        rt_b = time.perf_counter() - t0
        rows_baseline.append({
            "cycle": cycle, "reindexed": True,
            "tokens": tokens_b, "runtime_s": rt_b,
            "cost_usd": tokens_b / 1_000_000 * PRICE_PER_MILLION_TOKENS,
        })

        # ── HUPEDCARE: hash-gated ──────────────────────────────────────
        t0 = time.perf_counter()
        current_hash = md5_of_file(corpus)

        if current_hash == stored_hash:
            rt_h = time.perf_counter() - t0
            rows_hashed.append({
                "cycle": cycle, "reindexed": False,
                "tokens": 0, "runtime_s": rt_h, "cost_usd": 0.0,
            })
            action_h = "SKIP   "
        else:
            tokens_h, _ = mock_embed(corpus)
            rt_h = time.perf_counter() - t0
            stored_hash = current_hash
            rows_hashed.append({
                "cycle": cycle, "reindexed": True,
                "tokens": tokens_h, "runtime_s": rt_h,
                "cost_usd": tokens_h / 1_000_000 * PRICE_PER_MILLION_TOKENS,
            })
            action_h = "REINDEX"

        note = " <-- corpus changed" if cycle in change_days else ""
        print(f"  {cycle:>5}  {'REINDEX':>12}  {action_h:>12}{note}")

    shutil.rmtree(tmpdir)
    return rows_hashed, rows_baseline


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def _agg(rows: list[dict]) -> dict:
    return {
        "calls"    : sum(1 for r in rows if r["reindexed"]),
        "tokens"   : sum(r["tokens"]    for r in rows),
        "cost_usd" : sum(r["cost_usd"]  for r in rows),
        "avg_rt_ms": sum(r["runtime_s"] for r in rows) / len(rows) * 1000,
    }


def print_results_table(rows_hashed: list[dict], rows_baseline: list[dict]) -> bool:
    b = _agg(rows_baseline)
    h = _agg(rows_hashed)

    reduction_calls = (1 - h["calls"]    / b["calls"])    * 100
    reduction_cost  = (1 - h["cost_usd"] / b["cost_usd"]) * 100

    w_label = 42
    print(f"\n{'='*68}")
    print(f"  RESULTS — Minimum Quantitative Reporting Template (Table 5)")
    print(f"{'='*68}")
    print(f"  {'Metric':<{w_label}} {'Baseline':>10}  {'HUPEDCARE':>10}")
    print(f"  {'-'*65}")
    print(f"  {'Embedding API calls (30-day cycle)':<{w_label}} {b['calls']:>10}  {h['calls']:>10}")
    print(f"  {'Total tokens processed':<{w_label}} {b['tokens']:>10,}  {h['tokens']:>10,}")
    print(f"  {'Embedding API cost USD (30-day cycle)':<{w_label}} ${b['cost_usd']:>9.5f}  ${h['cost_usd']:>9.5f}")
    print(f"  {'Avg update runtime per cycle (ms)':<{w_label}} {b['avg_rt_ms']:>10.2f}  {h['avg_rt_ms']:>10.2f}")
    print(f"  {'-'*65}")
    print(f"  {'Embedding call reduction':<{w_label}} {'':>10}  {reduction_calls:>9.1f}%")
    print(f"  {'Cost reduction (H2 target: ≥85 %)':<{w_label}} {'':>10}  {reduction_cost:>9.1f}%")
    print(f"{'='*68}")

    passed = reduction_cost >= H2_THRESHOLD_PCT
    verdict = "PASS ✓" if passed else "FAIL ✗"
    print(f"\n  H2 hypothesis (≥{H2_THRESHOLD_PCT:.0f}% embedding cost reduction): [{verdict}]")
    print()
    return passed


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="H2 cost simulation — hash-gated vs stateless reindexing"
    )
    parser.add_argument(
        "--cycles", type=int, default=30,
        help="Number of update cycles to simulate (default: 30)"
    )
    parser.add_argument(
        "--changes", type=str, default=None,
        help="Comma-separated cycle numbers when corpus changes "
             f"(default: {DEFAULT_CHANGE_DAYS})"
    )
    parser.add_argument(
        "--corpus", type=str, default=DEFAULT_CORPUS,
        help="Path to master_context.txt (default: data/master_context.txt)"
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    if not os.path.exists(args.corpus):
        print(f"[ERROR] Corpus not found: {args.corpus}", file=sys.stderr)
        sys.exit(1)

    change_days = (
        [int(x) for x in args.changes.split(",")]
        if args.changes
        else DEFAULT_CHANGE_DAYS
    )

    rows_hashed, rows_baseline = run_simulation(
        corpus_src=args.corpus,
        cycles=args.cycles,
        change_days=change_days,
    )

    passed = print_results_table(rows_hashed, rows_baseline)
    sys.exit(0 if passed else 1)
