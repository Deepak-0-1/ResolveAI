"""
Optional RAGAS subset runner.

Requires: pip install -e ".[eval]" and a live LLM judge configuration.
This module does not invent scores — it only runs when explicitly invoked
and dependencies + credentials are present.
"""

from __future__ import annotations


def ragas_available() -> bool:
    try:
        import datasets  # noqa: F401
        import ragas  # noqa: F401

        return True
    except ImportError:
        return False


def run_ragas_subset_note() -> str:
    if not ragas_available():
        return (
            'RAGAS not installed. Install with `pip install -e ".[eval]"` '
            "and re-run with a configured judge LLM to compute faithfulness / context precision."
        )
    return (
        "RAGAS is installed. Wire your judge LLM in a follow-up run; "
        "do not paste placeholder scores into README."
    )


if __name__ == "__main__":
    print(run_ragas_subset_note())
