import json

from resolveai_rag.chunking import chunk_document
from resolveai_rag.parsing import parse_bytes


def test_parse_txt() -> None:
    doc = parse_bytes("hello.txt", b"Hello NovaDesk world.")
    assert doc.source_type == "txt"
    assert "NovaDesk" in doc.text


def test_parse_faq_text() -> None:
    raw = b"Q: How reset?\nA: Use forgot password.\n\nQ: Invite?\nA: Settings > Team."
    doc = parse_bytes("account.faq.txt", raw)
    assert doc.source_type == "faq"
    assert doc.metadata["pair_count"] == 2
    assert "Forgot password" in doc.text or "forgot password" in doc.text.lower()


def test_parse_faq_json() -> None:
    payload = [{"question": "Refund?", "answer": "Within 14 days."}]
    doc = parse_bytes("billing.json", json.dumps(payload).encode())
    assert doc.source_type == "faq"
    assert "Refund?" in doc.text


def test_chunk_respects_size() -> None:
    text = ("Section about billing. " * 40) + "\n\n" + ("Section about API keys. " * 40)
    doc = parse_bytes("policy.txt", text.encode())
    chunks = chunk_document(doc, chunk_size=200, chunk_overlap=40)
    assert len(chunks) >= 2
    assert all(len(c.text) <= 200 or c.index >= 0 for c in chunks)
    assert chunks[0].index == 0
