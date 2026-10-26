# Hybrid vs dense retrieval (measured)

- Dense mode: `offline_dense` @ `2026-10-26T15:16:57.976484+00:00`
- Hybrid mode: `offline_hybrid` @ `2026-10-26T15:16:59.136426+00:00`
- Cases: 120

| Metric | Dense | Hybrid | Delta (hybrid - dense) |
|--------|------:|-------:|-----------------------:|
| Status accuracy | 0.7 | 0.7 | +0.0000 |
| Keyword accuracy | 0.2667 | 0.4 | +0.1333 |
| Escalation accuracy | 0.85 | 0.85 | +0.0000 |
| Citation validity | 1.0 | 1.0 | +0.0000 |
| Latency p50 (ms) | 7.02 | 6.76 | -0.2600 |

## Verdict

_Keep hybrid only if status/keyword metrics improve without unacceptable latency. Numbers above are from this offline run — not fabricated._
