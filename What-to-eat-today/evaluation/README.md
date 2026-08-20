# Knowledge Base Evaluation

This directory contains a lightweight, repeatable evaluation for the recipe Graph RAG knowledge base.

## Metrics

- `pass_rate`: a question passes when the API succeeds and all `required_terms` appear in the answer.
- `mean_keyword_recall`: average proportion of `expected_terms` found in the generated answer.
- `avg_latency_seconds`: average end-to-end `/api/chat` latency.
- `p95_latency_seconds`: approximate p95 latency for the evaluated questions.

## Run

Start Neo4j, Milvus, the backend, and the frontend first. The backend defaults to `http://localhost:8002`.

```bash
cd What-to-eat-today
python evaluation/evaluate_kb.py
```

For a quick smoke run:

```bash
python evaluation/evaluate_kb.py --limit 3
```

Each run writes a JSON report to `evaluation/results/`.
