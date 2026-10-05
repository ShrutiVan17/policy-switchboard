import argparse
import hashlib
import json
from pathlib import Path
import time
from .benchmark import cases
from .engine import enforce, ENGINE_REVISION, resolve, VERDICTS


def summarize(rows, elapsed, cache_hits=0, backend="deterministic"):
    total = len(rows)
    correct = sum(r["expected"] == r["predicted"] for r in rows)
    violations = [r for r in rows if r["expected"] != "pass"]
    compliant = [r for r in rows if r["expected"] == "pass"]
    paired = {}
    for r in rows:
        if r["tenant"] == "harbor":
            paired.setdefault(r["family_id"], {})[r["version"]] = r
    changes, invariants = [], []
    for pair in paired.values():
        if "v1" in pair and "v2" in pair:
            a, b = pair["v1"], pair["v2"]
            (changes if a["expected"] != b["expected"] else invariants).append((a, b))
    def ratio(n, d):
        return round(n/d, 4) if d else None
    f1s = []
    for label in VERDICTS:
        tp = sum(r["expected"] == r["predicted"] == label for r in rows)
        fp = sum(r["predicted"] == label and r["expected"] != label for r in rows)
        fn = sum(r["expected"] == label and r["predicted"] != label for r in rows)
        f1s.append(2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0)
    latencies = sorted(r["latency_ms"] for r in rows if not r["cache_hit"])
    return {"backend": backend, "benchmark": "synthetic-smoke-v1", "total": total, "correct": correct,
            "accuracy": ratio(correct, total), "macro_f1": round(sum(f1s)/4, 4),
            "violation_cases": len(violations), "compliant_cases": len(compliant),
            "violation_recall": ratio(sum(r["predicted"] != "pass" for r in violations), len(violations)),
            "false_block_rate": ratio(sum(r["predicted"] != "pass" for r in compliant), len(compliant)),
            "changed_pairs": len(changes), "changed_pair_accuracy": ratio(sum(all(r["predicted"] == r["expected"] for r in pair) for pair in changes), len(changes)),
            "invariant_pairs": len(invariants), "invariant_pair_error_rate": ratio(sum(any(r["predicted"] != r["expected"] for r in pair) for pair in invariants), len(invariants)),
            "wall_ms": round(elapsed*1000, 3), "cache_hits": cache_hits,
            "p95_uncached_ms": round(latencies[min(len(latencies)-1, int(len(latencies)*.95))], 3) if latencies else None,
            "cost_usd": None, "gpu_seconds": None,
            "limitations": "Curated synthetic smoke cases, not an independent compliance benchmark. No GPU/model performance or cost measured.",
            "rows": rows}


def run(mode="full", cache=None):
    if mode not in ("full", "triage"):
        raise ValueError("mode must be full or triage")
    cache = cache if cache is not None else {}
    start = time.perf_counter()
    rows, hits = [], 0
    for case in cases():
        # Refund diff dependency + fixed non-refund invariant sentinels.
        if mode == "triage" and case["dependency"] != "REFUND-01" and case["family_id"] not in {"hello", "secret", "guarantee"}:
            continue
        config = {"engine": ENGINE_REVISION, "policy_hash": resolve(case["tenant"], case["version"]).digest,
                  "message": case["message"], "context": case["context"]}
        key = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
        hit = key in cache
        t = time.perf_counter()
        if not hit:
            cache[key] = enforce(case["message"], case["context"], case["tenant"], case["version"])["verdict"]
        hits += hit
        rows.append({**case, "predicted": cache[key], "cache_hit": hit, "latency_ms": round((time.perf_counter()-t)*1000, 4)})
    report = summarize(rows, time.perf_counter()-start, hits)
    report["mode"] = mode
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["full", "triage"], default="full")
    parser.add_argument("--output", default="artifacts/evaluation.json")
    args = parser.parse_args()
    report = run(args.mode)
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in report.items() if k != "rows"}, indent=2))
