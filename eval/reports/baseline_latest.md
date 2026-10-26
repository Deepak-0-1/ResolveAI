# ResolveAI evaluation report (offline_hash_fake_llm)

- Generated: `2026-10-26T15:11:06.849542+00:00`
- Dataset: `eval\datasets\golden_v1.jsonl` (120 cases)
- Docs indexed: `5`

## Summary metrics (measured)

| Metric | Value |
|--------|-------|
| Status accuracy | 0.7 |
| Keyword accuracy | 0.2667 |
| Escalation accuracy | 0.85 |
| Citation validity | 1.0 |
| Latency mean (ms) | 6.84 |
| Latency p50 (ms) | 6.5 |
| Latency max (ms) | 21.04 |

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
- Use --live with Ollama+Qdrant for stronger answer/citation quality measurement.
- RAGAS optional: install [eval] extras and pass --ragas once live LLM is available.
