# ResolveAI evaluation report (offline_dense)

- Generated: `2026-10-26T15:16:57.976484+00:00`
- Dataset: `eval\datasets\golden_v1.jsonl` (120 cases)
- Retrieval mode: `dense`
- Docs indexed: `5`

## Summary metrics (measured)

| Metric | Value |
|--------|-------|
| Status accuracy | 0.7 |
| Keyword accuracy | 0.2667 |
| Escalation accuracy | 0.85 |
| Citation validity | 1.0 |
| Latency mean (ms) | 7.81 |
| Latency p50 (ms) | 7.02 |
| Latency max (ms) | 18.16 |

## By kind

- **conflict**: n=10, status_accuracy=0.8000
- **escalation**: n=20, status_accuracy=0.8500
- **injection**: n=10, status_accuracy=0.9000
- **irrelevant**: n=15, status_accuracy=0.0000
- **missing**: n=15, status_accuracy=0.0000
- **normal**: n=30, status_accuracy=1.0000
- **paraphrase**: n=20, status_accuracy=1.0000

## Notes

- Metrics are from this run only — not fabricated.
- Offline mode uses HashEmbedder+FakeLLM; lexical/semantic quality is limited.
- Hybrid = dense + BM25 fused with Reciprocal Rank Fusion (RRF).
- Use --live with Ollama+Qdrant for stronger answer-quality measurement.
