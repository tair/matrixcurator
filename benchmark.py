"""
MB4 Curator – Benchmark Script
===============================
Runs each benchmark PDF through the process-pdf API and records:
  • wall-clock time
  • token usage (prompt, completion, cached, total, llm_calls)
  • extraction accuracy vs KEY.nex ground truth

Usage:
    python benchmark.py                        # default: http://localhost:8001
    python benchmark.py --url http://host:8001 # custom API URL
    python benchmark.py --tag "after-v2-prompt" # label this run

Results are appended to  src/data/benchmarks/results.json
"""

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from difflib import SequenceMatcher

import requests

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BENCHMARKS_DIR = Path(__file__).resolve().parent / "src" / "data" / "benchmarks"
RESULTS_FILE = BENCHMARKS_DIR / "results.json"

# Benchmark PDFs and their expected character counts from KEY.nex NCHAR
BENCHMARK_PDFS = [
    {"pdf": "Lepidocystoidea_Nohejlova_et_al_2019.pdf",   "key": "Lepidocystoidea_Nohejlova_et_al_2019_KEY.nex",   "nchar": 15},
    {"pdf": "Oryctocephalinae_Sundberg_2006.pdf",          "key": "Oryctocephalinae_Sundberg_2006_KEY.nex",          "nchar": 20},
    {"pdf": "Dicranograptidae_Song_&_Zhang_2014.pdf",      "key": "Dicranograptidae_Song_&_Zhang_2014_KEY.nex",      "nchar": 25},
    {"pdf": "Mesozoic_Echinoidea_Smith_2007.pdf",          "key": "Mesozoic_Echinoidea_Smith_2007_KEY.nex",          "nchar": 61},
    {"pdf": "Velatida_Gale_2018.pdf",                      "key": "Velatida_Gale_2018_KEY.nex",                      "nchar": 63},
    {"pdf": "Ursidae_Abella_et_al_2012.pdf",               "key": "Ursidae_Abella_et_al_2012_KEY.nex",               "nchar": 82},
    {"pdf": "Ichthyosauria_Thorne_et_al_2011.pdf",         "key": "Ichthyosauria_Thorne_et_al_2011_KEY.nex",         "nchar": 105},
]

# Approximate Gemini pricing (USD per 1M tokens) – update as needed
PRICING = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.5-pro":   {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash":  {"input": 0.10, "output": 0.40},
}


# ---------------------------------------------------------------------------
# KEY.nex parser – extract ground-truth character names & states
# ---------------------------------------------------------------------------
def parse_key_nex(path: Path) -> list[dict]:
    """
    Parse a NEXUS KEY file and return a list of ground-truth characters.
    Each entry: {"index": int, "name": str, "states": [str, ...]}
    Returns empty list if CHARSTATELABELS block is not found.
    """
    text = path.read_text(encoding="utf-8", errors="replace")

    # Find CHARSTATELABELS block
    match = re.search(r"CHARSTATELABELS\s*\n(.*?);\s*\n", text, re.DOTALL | re.IGNORECASE)
    if not match:
        return []

    block = match.group(1)
    characters = []

    # Pattern: index 'name' / 'state0' 'state1' ...   OR   index name / state0 state1 ...
    # Each character entry ends with a comma or the end of the block
    entries = re.split(r",\s*\n", block.strip())
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue

        # Extract index and name
        # Format:  1 'Sicular length (mm)' / 'state0' 'state1'
        # OR:      1 Name_without_quotes / state0 state1
        m = re.match(r"(\d+)\s+'([^']+)'\s*/\s*(.*)", entry, re.DOTALL)
        if not m:
            m = re.match(r"(\d+)\s+(\S+)\s*/\s*(.*)", entry, re.DOTALL)
        if not m:
            continue

        idx = int(m.group(1))
        name = m.group(2).strip().replace("_", " ")
        states_raw = m.group(3).strip()

        # Parse states: 'state name' or state_name separated by spaces or quotes
        states = re.findall(r"'([^']*)'", states_raw)
        if not states:
            states = [s.replace("_", " ") for s in states_raw.split() if s]

        characters.append({"index": idx, "name": name, "states": states})

    return characters


# ---------------------------------------------------------------------------
# Accuracy comparison
# ---------------------------------------------------------------------------
def normalize(s: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for comparison."""
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return re.sub(r"\s+", " ", s)


def best_match_score(extracted_name: str, ground_truth_names: list[str]) -> tuple[float, str]:
    """Return (best_similarity_ratio, matched_gt_name) using SequenceMatcher."""
    norm_ext = normalize(extracted_name)
    best_score = 0.0
    best_gt = ""
    for gt in ground_truth_names:
        norm_gt = normalize(gt)
        score = SequenceMatcher(None, norm_ext, norm_gt).ratio()
        if score > best_score:
            best_score = score
            best_gt = gt
    return best_score, best_gt


def compare_extraction(extracted: list[dict], ground_truth: list[dict]) -> dict:
    """
    Compare extracted characters against ground truth.
    Returns accuracy metrics.
    """
    if not ground_truth:
        # No CHARSTATELABELS in KEY file – can only compare counts
        return {
            "ground_truth_chars": 0,
            "extracted_chars": len(extracted),
            "exact_matches": None,
            "fuzzy_matches_70": None,
            "fuzzy_matches_50": None,
            "accuracy_pct": None,
            "note": "No CHARSTATELABELS in KEY file – accuracy comparison unavailable",
        }

    gt_names = [c["name"] for c in ground_truth]
    ext_names = [c.get("character", "") for c in extracted]

    exact = 0
    fuzzy_70 = 0  # >= 70% similarity
    fuzzy_50 = 0  # >= 50% similarity
    matches_detail = []

    for ext_name in ext_names:
        score, matched = best_match_score(ext_name, gt_names)
        if score >= 0.95:
            exact += 1
        if score >= 0.70:
            fuzzy_70 += 1
        if score >= 0.50:
            fuzzy_50 += 1
        matches_detail.append({
            "extracted": ext_name,
            "best_gt_match": matched,
            "similarity": round(score, 3),
        })

    return {
        "ground_truth_chars": len(gt_names),
        "extracted_chars": len(ext_names),
        "exact_matches": exact,
        "fuzzy_matches_70": fuzzy_70,
        "fuzzy_matches_50": fuzzy_50,
        "accuracy_pct": round(fuzzy_70 / len(gt_names) * 100, 1) if gt_names else 0,
        "matches_detail": matches_detail,
    }


# ---------------------------------------------------------------------------
# Estimate cost
# ---------------------------------------------------------------------------
def estimate_cost(token_usage: dict, extraction_model: str, evaluation_model: str) -> dict:
    """Rough cost estimate based on Gemini pricing."""
    # The API currently uses extraction model for extraction calls and evaluation model for evaluation calls.
    # We can't split prompt/completion between the two from the aggregate, so we use a blended approach.
    # Prompt tokens are mostly input (from PDF context), completion tokens are output.
    prompt_tokens = token_usage.get("prompt_tokens", 0)
    completion_tokens = token_usage.get("completion_tokens", 0)

    # Use extraction model pricing for input (most tokens come from context)
    ext_pricing = PRICING.get(extraction_model, {"input": 0.15, "output": 0.60})
    eval_pricing = PRICING.get(evaluation_model, {"input": 1.25, "output": 10.00})

    # Rough split: assume 60% of prompt tokens go to extraction, 40% to evaluation
    ext_input_cost = (prompt_tokens * 0.6 / 1_000_000) * ext_pricing["input"]
    eval_input_cost = (prompt_tokens * 0.4 / 1_000_000) * eval_pricing["input"]
    ext_output_cost = (completion_tokens * 0.6 / 1_000_000) * ext_pricing["output"]
    eval_output_cost = (completion_tokens * 0.4 / 1_000_000) * eval_pricing["output"]

    total = ext_input_cost + eval_input_cost + ext_output_cost + eval_output_cost

    return {
        "estimated_cost_usd": round(total, 6),
        "cost_breakdown": {
            "extraction_input": round(ext_input_cost, 6),
            "evaluation_input": round(eval_input_cost, 6),
            "extraction_output": round(ext_output_cost, 6),
            "evaluation_output": round(eval_output_cost, 6),
        },
    }


# ---------------------------------------------------------------------------
# Run one benchmark
# ---------------------------------------------------------------------------
def run_single_benchmark(api_url: str, pdf_info: dict) -> dict:
    """Run process-pdf for a single benchmark PDF and return results."""
    pdf_path = BENCHMARKS_DIR / pdf_info["pdf"]
    key_path = BENCHMARKS_DIR / pdf_info["key"]

    if not pdf_path.exists():
        return {"pdf": pdf_info["pdf"], "error": f"PDF not found: {pdf_path}"}

    # Parse ground truth
    ground_truth = parse_key_nex(key_path) if key_path.exists() else []

    # Call the API
    url = f"{api_url.rstrip('/')}/api/process-pdf"
    print(f"\n{'='*60}")
    print(f"  📄 {pdf_info['pdf']}")
    print(f"  Ground truth: {pdf_info['nchar']} characters")
    print(f"  API: {url}")
    print(f"{'='*60}")

    start = time.time()
    try:
        with open(pdf_path, "rb") as f:
            files = {"pdf_file": (pdf_info["pdf"], f, "application/pdf")}
            data = {
                "total_characters": str(pdf_info["nchar"]),
                "page_range": "all",
                "zero_indexed": "false",
            }
            resp = requests.post(url, files=files, data=data, timeout=300)
        wall_time = round(time.time() - start, 2)
    except requests.exceptions.ConnectionError:
        return {"pdf": pdf_info["pdf"], "error": "Connection refused – is the API running?"}
    except requests.exceptions.Timeout:
        return {"pdf": pdf_info["pdf"], "error": "Request timed out (>300s)"}

    if resp.status_code != 200:
        return {
            "pdf": pdf_info["pdf"],
            "error": f"HTTP {resp.status_code}: {resp.text[:500]}",
            "wall_time_seconds": wall_time,
        }

    result = resp.json()
    metadata = result.get("metadata", {})
    token_usage = result.get("token_usage", {})
    character_states = result.get("character_states", [])
    failed_indexes = result.get("failed_indexes", [])

    # Compare with ground truth
    accuracy = compare_extraction(character_states, ground_truth)

    # Estimate cost
    extraction_model = metadata.get("extraction_model", "Gemini 2.5 Flash")
    evaluation_model = metadata.get("evaluation_model", "Gemini 2.5 Pro")
    # Map friendly names to API IDs for pricing lookup
    model_map = {"Gemini 2.5 Flash": "gemini-2.5-flash", "Gemini 2.5 Pro": "gemini-2.5-pro", "Gemini 2.0 Flash": "gemini-2.0-flash"}
    cost = estimate_cost(
        token_usage,
        model_map.get(extraction_model, "gemini-2.5-flash"),
        model_map.get(evaluation_model, "gemini-2.5-pro"),
    )

    # Print summary
    print(f"  ✅ Extracted: {len(character_states)}/{pdf_info['nchar']} characters")
    print(f"  ❌ Failed:    {len(failed_indexes)}")
    if accuracy.get("accuracy_pct") is not None:
        print(f"  🎯 Accuracy:  {accuracy['accuracy_pct']}% (fuzzy ≥70%)")
    print(f"  ⏱  Time:      {wall_time}s (API reported: {metadata.get('processing_time_seconds', '?')}s)")
    print(f"  🪙 Tokens:    {token_usage.get('total_tokens', '?')} total ({token_usage.get('llm_calls', '?')} LLM calls)")
    print(f"  💰 Est. cost: ${cost['estimated_cost_usd']:.4f}")

    return {
        "pdf": pdf_info["pdf"],
        "ground_truth_nchar": pdf_info["nchar"],
        "wall_time_seconds": wall_time,
        "api_time_seconds": metadata.get("processing_time_seconds"),
        "extraction_model": extraction_model,
        "evaluation_model": evaluation_model,
        "successful_extractions": len(character_states),
        "failed_extractions": len(failed_indexes),
        "failed_indexes": failed_indexes,
        "token_usage": token_usage,
        "cost": cost,
        "accuracy": {k: v for k, v in accuracy.items() if k != "matches_detail"},
        "matches_detail": accuracy.get("matches_detail", []),
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="MB4 Curator Benchmark")
    parser.add_argument("--url", default="http://localhost:8001", help="Curator API base URL")
    parser.add_argument("--tag", default="", help="Label for this benchmark run (e.g. 'baseline', 'after-batch-prompt')")
    parser.add_argument("--pdf", default=None, help="Run only a specific PDF (partial name match)")
    args = parser.parse_args()

    # Filter PDFs if requested
    pdfs = BENCHMARK_PDFS
    if args.pdf:
        pdfs = [p for p in pdfs if args.pdf.lower() in p["pdf"].lower()]
        if not pdfs:
            print(f"❌ No benchmark PDF matching '{args.pdf}'")
            sys.exit(1)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    print(f"\n🚀 MB4 Curator Benchmark – Run {run_id}")
    print(f"   Tag: {args.tag or '(none)'}")
    print(f"   API: {args.url}")
    print(f"   PDFs: {len(pdfs)}")

    results = []
    total_time = 0
    total_cost = 0
    total_tokens = 0

    for pdf_info in pdfs:
        r = run_single_benchmark(args.url, pdf_info)
        results.append(r)
        if "error" not in r:
            total_time += r.get("wall_time_seconds", 0)
            total_cost += r.get("cost", {}).get("estimated_cost_usd", 0)
            total_tokens += r.get("token_usage", {}).get("total_tokens", 0)

    # Print summary table
    print(f"\n{'='*80}")
    print(f"  BENCHMARK SUMMARY – {run_id}  {f'[{args.tag}]' if args.tag else ''}")
    print(f"{'='*80}")
    print(f"  {'PDF':<45} {'Chars':>6} {'Time':>7} {'Tokens':>10} {'Cost':>8} {'Acc%':>6}")
    print(f"  {'-'*45} {'-'*6} {'-'*7} {'-'*10} {'-'*8} {'-'*6}")
    for r in results:
        if "error" in r:
            print(f"  {r['pdf']:<45} {'ERROR':>6}  {r.get('error', '')[:30]}")
        else:
            acc = r.get("accuracy", {}).get("accuracy_pct", "N/A")
            acc_str = f"{acc}%" if acc is not None else "N/A"
            print(f"  {r['pdf']:<45} {r['successful_extractions']:>3}/{r['ground_truth_nchar']:<2} {r['wall_time_seconds']:>6.1f}s {r['token_usage'].get('total_tokens', 0):>10,} ${r['cost']['estimated_cost_usd']:>7.4f} {acc_str:>6}")

    print(f"  {'-'*45} {'-'*6} {'-'*7} {'-'*10} {'-'*8}")
    print(f"  {'TOTAL':<45} {'':>6} {total_time:>6.1f}s {total_tokens:>10,} ${total_cost:>7.4f}")
    print()

    # Save to results file
    run_record = {
        "run_id": run_id,
        "tag": args.tag,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "api_url": args.url,
        "totals": {
            "wall_time_seconds": round(total_time, 2),
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(total_cost, 6),
            "pdfs_tested": len(pdfs),
        },
        "results": results,
    }

    # Load existing results or start fresh
    all_runs = []
    if RESULTS_FILE.exists():
        try:
            all_runs = json.loads(RESULTS_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, Exception):
            all_runs = []

    all_runs.append(run_record)
    RESULTS_FILE.write_text(json.dumps(all_runs, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  📁 Results saved to {RESULTS_FILE}")
    print(f"     Total benchmark runs stored: {len(all_runs)}")


if __name__ == "__main__":
    main()


