#!/usr/bin/env python3
"""
H3 Structural Explainability Test — RAGAS Faithfulness + Source-Citation Compliance
=====================================================================================
Validates H3 by running the full RAG pipeline (ChromaDB retrieval + LLM generation)
in two conditions:
  - WITH_PROVENANCE : corpus has --- SOURCE: --- headers (production HUPEDCARE)
  - NO_PROVENANCE   : same corpus stripped of source headers (baseline)

Metrics collected per condition:
  1. RAGAS Faithfulness score  (0–1): fraction of answer claims supported by context
  2. Unsupported-claim rate (%): 1 - faithfulness, expressed as percentage
  3. Source-citation compliance (%): fraction of answers that explicitly cite a source

Usage:
    python scripts/test_h3_ragas.py
    python scripts/test_h3_ragas.py --top-k 6 --questions 15
"""

import argparse
import os
import re
import sys
import time
import warnings

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# 20 clinically grounded questions — all answerable from master_context.txt
# ---------------------------------------------------------------------------
QUESTIONS = [
    "What is the FLACC scale and what does a score of 7 or above indicate?",
    "At what age can children reliably use the Numerical Rating Scale for pain?",
    "What is the recommended oral dose of paracetamol for a child weighing 20 kg?",
    "Why is codeine contraindicated in children under 12 years?",
    "What non-pharmacological interventions are recommended for procedural pain in neonates?",
    "What does the WHO two-step analgesic ladder recommend for moderate to severe pain in children?",
    "What is the recommended dose of IV morphine for an opioid-naive child?",
    "How should pain be reassessed after administering an oral analgesic to a child?",
    "What are the signs of opioid-induced respiratory depression in children?",
    "What is the Faces Pain Scale Revised and for which age group is it validated?",
    "What is the CRIES scale used for and what score indicates significant pain?",
    "What is the role of sucrose solution in neonatal pain management?",
    "What are the key principles of the WHO guidelines for pediatric pain management?",
    "What is the recommended dose of ibuprofen for children and what are its contraindications?",
    "What is chronic pain in children and what are the most common types?",
    "What is multimodal analgesia and why is it recommended in pediatric surgery?",
    "What is kangaroo care and what is its evidence base for neonatal pain?",
    "What is the HUPEDCARE project and what are its main objectives?",
    "What analgesic protocol is recommended for a child in sickle cell vaso-occlusive crisis?",
    "What post-operative analgesic regimen is recommended at discharge after major pediatric surgery?",
]

# Regex: only count EXPLICIT source-filename citations, not generic attributions.
# With provenance headers the LLM cites "(source: who_guidelines.pdf)";
# without headers it can only produce generic phrases which are excluded here.
SOURCE_CITATION_PATTERNS = [
    r"\(source\s*:\s*\S+\)",         # (source: filename.pdf)
    r"\(fuente\s*:\s*\S+\)",         # Spanish variant
    r"\(fonte\s*:\s*\S+\)",          # Portuguese variant
    r"source\s*:\s*[\w_\-\.]+\.\w+", # source: filename.ext (bare)
    r"source\s*:\s*data\s+base",     # (source: data base) — DB entries
    r"fuente\s*:\s*base\s+de\s+datos",
]
_CITATION_RE = re.compile("|".join(SOURCE_CITATION_PATTERNS), re.IGNORECASE)


# ---------------------------------------------------------------------------
# RAG pipeline (mirrors server.py exactly, without HTTP layer)
# ---------------------------------------------------------------------------

def build_pipeline(data_folder: str, top_k: int):
    """Return (collection, openai_client, config) ready for inference."""
    import chromadb
    from chromadb.utils import embedding_functions
    from openai import OpenAI
    import yaml

    api_key = os.getenv("MODEL_API_KEY")

    _script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = os.path.join(_script_dir, "..", "config", "config.yaml")
    with open(config_path, "r") as fh:
        config = yaml.safe_load(fh)

    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=api_key,
        model_name=config["embeddings"]["embedding_model"],
    )
    db_path = os.path.join(data_folder, "vector_db")
    chroma_client = chromadb.PersistentClient(path=db_path)
    collection = chroma_client.get_or_create_collection(
        name="rag_context", embedding_function=openai_ef
    )
    llm = OpenAI(
        base_url=config["ai"].get("base_url"),
        api_key=api_key,
    )
    return collection, llm, config, top_k


def ask(question: str, collection, llm, config, top_k: int) -> tuple[str, list[str]]:
    """Run a single RAG query. Returns (answer, retrieved_contexts)."""
    results = collection.query(query_texts=[question], n_results=top_k)
    contexts: list[str] = results["documents"][0] if results["documents"] else []
    context_block = "\n\n".join(contexts)

    system_prompt = config["ai"]["system_prompt"]
    response = llm.chat.completions.create(
        model=config["ai"]["model"],
        temperature=config["embeddings"].get("temperature", 0.0),
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"RETRIEVED CONTEXT:\n{context_block}\n\n"
                    f"QUESTION: {question}"
                ),
            },
        ],
    )
    answer = response.choices[0].message.content
    return answer, contexts


# ---------------------------------------------------------------------------
# RAGAS faithfulness scoring
# ---------------------------------------------------------------------------

def compute_faithfulness(samples: list[dict]) -> float:
    """
    LLM-as-judge faithfulness (same algorithm as RAGAS):
      1. Extract discrete factual claims from each answer.
      2. For each claim ask the LLM whether it is supported by the retrieved contexts.
      3. Faithfulness = supported_claims / total_claims  (mean over samples).
    """
    from openai import OpenAI

    api_key = os.getenv("MODEL_API_KEY")
    client  = OpenAI(api_key=api_key)

    CLAIM_PROMPT = (
        "List every distinct factual claim in the following answer as a numbered list. "
        "Be granular — one claim per line. Output only the numbered list, nothing else.\n\n"
        "Answer:\n{answer}"
    )
    VERIFY_PROMPT = (
        "Context:\n{context}\n\n"
        "Claim: {claim}\n\n"
        "Is this claim fully supported by the context above? "
        "Reply with exactly one word: YES or NO."
    )

    sample_scores = []
    for s in samples:
        answer   = s["answer"]
        context  = "\n\n".join(s["contexts"])

        # Step 1 — extract claims
        resp = client.chat.completions.create(
            model="gpt-4o-mini-2024-07-18",
            temperature=0,
            messages=[{"role": "user", "content": CLAIM_PROMPT.format(answer=answer)}],
        )
        raw = resp.choices[0].message.content.strip()
        claims = [re.sub(r"^\d+[\.\)]\s*", "", line).strip()
                  for line in raw.splitlines() if line.strip()]

        if not claims:
            sample_scores.append(1.0)
            continue

        # Step 2 — verify each claim against context
        supported = 0
        for claim in claims:
            vresp = client.chat.completions.create(
                model="gpt-4o-mini-2024-07-18",
                temperature=0,
                messages=[{"role": "user",
                           "content": VERIFY_PROMPT.format(context=context, claim=claim)}],
            )
            verdict = vresp.choices[0].message.content.strip().upper()
            if verdict.startswith("YES"):
                supported += 1
            time.sleep(0.1)

        sample_scores.append(supported / len(claims))

    return sum(sample_scores) / len(sample_scores) if sample_scores else 0.0


# ---------------------------------------------------------------------------
# Source-citation compliance
# ---------------------------------------------------------------------------

def citation_compliance(answers: list[str]) -> float:
    """Fraction of answers that contain at least one source citation."""
    hits = sum(1 for a in answers if _CITATION_RE.search(a))
    return hits / len(answers) if answers else 0.0


# ---------------------------------------------------------------------------
# Main simulation
# ---------------------------------------------------------------------------

def run_condition(
    label: str,
    questions: list[str],
    collection,
    llm,
    config,
    top_k: int,
    cache_path: str | None = None,
) -> dict:
    print(f"\n  Running condition: {label}")
    print(f"  {'-'*52}")

    import json as _json

    if cache_path and os.path.exists(cache_path):
        with open(cache_path) as fh:
            samples = _json.load(fh)
        answers = [s["answer"] for s in samples]
        print(f"  (loaded {len(samples)} cached samples from {cache_path})")
    else:
        samples = []
        answers = []
        for i, q in enumerate(questions, 1):
            answer, contexts = ask(q, collection, llm, config, top_k)
            samples.append({"question": q, "answer": answer, "contexts": contexts})
            answers.append(answer)
            cited = "✓" if _CITATION_RE.search(answer) else "✗"
            short_q = q[:55] + "…" if len(q) > 55 else q
            print(f"  [{i:02d}] [{cited}] {short_q}")
            time.sleep(0.3)

        if cache_path:
            os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
            with open(cache_path, "w") as fh:
                _json.dump(samples, fh, indent=2)

    print(f"\n  Computing faithfulness ({len(samples)} samples)…")
    faithfulness_score = compute_faithfulness(samples)
    citation_rate      = citation_compliance(answers)

    return {
        "label":             label,
        "n":                 len(samples),
        "faithfulness":      faithfulness_score,
        "unsupported_rate":  (1 - faithfulness_score) * 100,
        "citation_rate":     citation_rate * 100,
        "answers":           answers,
        "samples":           samples,
    }


def print_results_table(with_prov: dict, no_prov: dict) -> bool:
    w = 46
    print(f"\n{'='*70}")
    print(f"  RESULTS — H3 Structural Explainability (RAGAS + Citation Audit)")
    print(f"{'='*70}")
    print(f"  {'Metric':<{w}} {'Baseline':>10}  {'HUPEDCARE':>10}")
    print(f"  {'-'*67}")
    print(f"  {'Faithfulness / grounding score (RAGAS)':<{w}} "
          f"{no_prov['faithfulness']:>10.3f}  {with_prov['faithfulness']:>10.3f}")
    print(f"  {'Unsupported-claim rate (%)':<{w}} "
          f"{no_prov['unsupported_rate']:>9.1f}%  {with_prov['unsupported_rate']:>9.1f}%")
    print(f"  {'Source-citation compliance (%)':<{w}} "
          f"{no_prov['citation_rate']:>9.1f}%  {with_prov['citation_rate']:>9.1f}%")
    print(f"{'='*70}")

    faith_improved  = with_prov["faithfulness"]  >= no_prov["faithfulness"]
    citation_better = with_prov["citation_rate"] >  no_prov["citation_rate"]
    h3_pass = faith_improved and citation_better
    verdict = "PASS ✓" if h3_pass else "FAIL ✗"

    print(f"\n  H3 hypothesis (provenance improves grounding + citation): [{verdict}]")
    print(f"    {'OK' if faith_improved  else 'FAIL'}  Faithfulness: "
          f"{no_prov['faithfulness']:.3f} → {with_prov['faithfulness']:.3f}")
    print(f"    {'OK' if citation_better else 'FAIL'}  Citation compliance: "
          f"{no_prov['citation_rate']:.1f}% → {with_prov['citation_rate']:.1f}%")
    print()
    return h3_pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="H3 RAGAS + citation compliance test")
    parser.add_argument("--top-k",    type=int, default=6,  help="Chunks retrieved per query (default: 6)")
    parser.add_argument("--questions", type=int, default=len(QUESTIONS),
                        help=f"Number of questions to use (default: {len(QUESTIONS)})")
    return parser.parse_args()


def main() -> int:
    from dotenv import load_dotenv
    load_dotenv()

    args = parse_args()
    n_q = min(args.questions, len(QUESTIONS))
    questions = QUESTIONS[:n_q]

    _script_dir = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(_script_dir, "..", "data")

    collection, llm, config, top_k = build_pipeline(data_folder, args.top_k)

    print(f"\n{'='*70}")
    print(f"  H3 — Structural Explainability Test")
    print(f"  Questions: {n_q}  |  top-K: {top_k}  |  model: {config['ai']['model']}")
    print(f"{'='*70}")

    _cache_dir = os.path.join(_script_dir, "..", "data", "h3_cache")

    # Condition 1: WITH provenance (production corpus — already indexed)
    with_prov = run_condition(
        "WITH_PROVENANCE (HUPEDCARE)", questions, collection, llm, config, top_k,
        cache_path=os.path.join(_cache_dir, "with_provenance.json"),
    )

    # Condition 2: NO provenance — re-index corpus with SOURCE headers stripped
    print("\n  Re-indexing corpus without provenance headers for baseline…")
    import chromadb as _chromadb
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from chromadb.utils import embedding_functions as _ef
    import yaml

    config_path = os.path.join(_script_dir, "..", "config", "config.yaml")
    with open(config_path) as fh:
        _cfg = yaml.safe_load(fh)

    master_path = os.path.join(data_folder, "master_context.txt")
    with open(master_path, "r", encoding="utf-8") as fh:
        corpus_with = fh.read()

    # Strip all --- SOURCE: ... --- headers from the corpus
    corpus_stripped = re.sub(r"\n?--- SOURCE: .+? ---\n?", "\n", corpus_with)

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=_cfg["embeddings"]["max_chunk_size"],
        chunk_overlap=_cfg["embeddings"]["chunk_overlap"],
        separators=["\n\n", "\n", " ", ""],
    )
    chunks_stripped = splitter.split_text(corpus_stripped)

    api_key = os.getenv("MODEL_API_KEY")
    openai_ef_bl = _ef.OpenAIEmbeddingFunction(
        api_key=api_key, model_name=_cfg["embeddings"]["embedding_model"]
    )
    db_path = os.path.join(data_folder, "vector_db")
    chroma_bl = _chromadb.PersistentClient(path=db_path)

    # Use a separate collection name so we don't destroy the production index
    BL_COLLECTION = "rag_context_no_provenance"
    if BL_COLLECTION in [c.name for c in chroma_bl.list_collections()]:
        chroma_bl.delete_collection(BL_COLLECTION)
    coll_bl = chroma_bl.create_collection(name=BL_COLLECTION, embedding_function=openai_ef_bl)

    BATCH = 150
    for i in range(0, len(chunks_stripped), BATCH):
        batch = chunks_stripped[i: i + BATCH]
        coll_bl.add(documents=batch, ids=[f"bl_{j}" for j in range(i, i + len(batch))])
        time.sleep(0.5)
    print(f"  Baseline index: {len(chunks_stripped)} chunks (no SOURCE headers)")

    no_prov = run_condition(
        "NO_PROVENANCE (baseline)", questions, coll_bl, llm, config, top_k,
        cache_path=os.path.join(_cache_dir, "no_provenance.json"),
    )

    # Clean up baseline collection
    chroma_bl.delete_collection(BL_COLLECTION)

    passed = print_results_table(with_prov, no_prov)
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
