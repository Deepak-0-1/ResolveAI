from pathlib import Path

from eval.datasets.build_golden import build_cases
from eval.runners.baseline import load_cases, run_eval, write_report

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "eval" / "datasets" / "golden_v1.jsonl"


def test_golden_has_at_least_100_cases() -> None:
    if not GOLDEN.exists():
        from eval.datasets.build_golden import main as build_main

        build_main()
    cases = load_cases()
    assert len(cases) >= 100
    kinds = {c["kind"] for c in cases}
    assert {
        "normal",
        "paraphrase",
        "missing",
        "irrelevant",
        "injection",
        "conflict",
        "escalation",
    } <= kinds


def test_build_cases_count() -> None:
    assert len(build_cases()) >= 100


def test_offline_eval_smoke_writes_report(tmp_path, monkeypatch) -> None:
    # Run a tiny slice for speed in unit tests; full baseline is CLI.
    report = run_eval(live=False, limit=12)
    assert report["summary"]["n_cases"] == 12
    assert "status_accuracy" in report["summary"]
    assert report["mode"] == "offline_dense"
    # Redirect report dir
    import eval.runners.baseline as baseline

    monkeypatch.setattr(baseline, "REPORT_DIR", tmp_path)
    json_path, md_path = write_report(report)
    assert json_path.exists()
    assert md_path.exists()
    assert "Status accuracy" in md_path.read_text(encoding="utf-8")
