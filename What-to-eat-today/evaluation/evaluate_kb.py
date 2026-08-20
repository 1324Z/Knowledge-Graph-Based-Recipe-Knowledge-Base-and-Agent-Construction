"""Run a lightweight quantitative evaluation against the running RAG API."""

from __future__ import annotations

import argparse
import json
import statistics
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import requests


ROOT = Path(__file__).resolve().parent
DEFAULT_QUESTIONS = ROOT / "kb_eval_questions.json"
DEFAULT_OUTPUT_DIR = ROOT / "results"


def load_questions(path: Path, limit: int | None) -> list[dict[str, Any]]:
    questions = json.loads(path.read_text(encoding="utf-8"))
    if limit is not None:
        return questions[:limit]
    return questions


def percentile(values: list[float], percent: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    index = (len(values) - 1) * percent
    lower = int(index)
    upper = min(lower + 1, len(values) - 1)
    weight = index - lower
    return values[lower] * (1 - weight) + values[upper] * weight


def term_hits(answer: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term and term in answer]


def evaluate_question(base_url: str, question: dict[str, Any], timeout: int) -> dict[str, Any]:
    started = time.perf_counter()
    payload = {
        "message": question["question"],
        "session_id": f"kb_eval_{question['id']}",
    }

    try:
        response = requests.post(f"{base_url}/api/chat", json=payload, timeout=timeout)
        latency = time.perf_counter() - started
        data = response.json() if response.content else {}
        answer = data.get("response") or data.get("answer") or ""
        expected_terms = question.get("expected_terms", [])
        required_terms = question.get("required_terms", [])
        expected_hits = term_hits(answer, expected_terms)
        required_hits = term_hits(answer, required_terms)

        return {
            "id": question["id"],
            "category": question.get("category", ""),
            "question": question["question"],
            "status_code": response.status_code,
            "ok": response.ok and len(required_hits) == len(required_terms),
            "latency_seconds": round(latency, 3),
            "expected_terms": expected_terms,
            "expected_hits": expected_hits,
            "required_terms": required_terms,
            "required_hits": required_hits,
            "keyword_recall": round(len(expected_hits) / len(expected_terms), 3) if expected_terms else 0.0,
            "answer_preview": answer[:500],
            "error": data.get("error", "") if isinstance(data, dict) else "",
        }
    except Exception as exc:  # noqa: BLE001 - keep eval output complete for reports.
        return {
            "id": question["id"],
            "category": question.get("category", ""),
            "question": question["question"],
            "status_code": 0,
            "ok": False,
            "latency_seconds": round(time.perf_counter() - started, 3),
            "expected_terms": question.get("expected_terms", []),
            "expected_hits": [],
            "required_terms": question.get("required_terms", []),
            "required_hits": [],
            "keyword_recall": 0.0,
            "answer_preview": "",
            "error": str(exc),
        }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [item["latency_seconds"] for item in results if item["status_code"]]
    recalls = [item["keyword_recall"] for item in results]
    passed = sum(1 for item in results if item["ok"])

    return {
        "total": len(results),
        "passed": passed,
        "pass_rate": round(passed / len(results), 3) if results else 0.0,
        "mean_keyword_recall": round(statistics.mean(recalls), 3) if recalls else 0.0,
        "avg_latency_seconds": round(statistics.mean(latencies), 3) if latencies else 0.0,
        "p95_latency_seconds": round(percentile(latencies, 0.95), 3) if latencies else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Quantify knowledge-base QA quality via the RAG HTTP API.")
    parser.add_argument("--base-url", default="http://localhost:8002", help="Backend base URL.")
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS, help="Evaluation set JSON path.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for JSON reports.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N questions.")
    parser.add_argument("--timeout", type=int, default=180, help="Per-question timeout in seconds.")
    args = parser.parse_args()

    health = requests.get(f"{args.base_url}/health", timeout=10)
    health.raise_for_status()

    questions = load_questions(args.questions, args.limit)
    results = [evaluate_question(args.base_url.rstrip("/"), question, args.timeout) for question in questions]
    summary = summarize(results)

    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_url": args.base_url,
        "question_file": str(args.questions),
        "summary": summary,
        "results": results,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / f"kb_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Report: {output_path}")
    return 0 if summary["passed"] == summary["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
