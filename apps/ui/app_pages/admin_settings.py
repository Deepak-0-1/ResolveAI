"""System Settings & Infrastructure Health — Live probes, active configuration, and security posture."""

from __future__ import annotations

import streamlit as st
from api_client import get_system_health
from theme import (
    apply_theme,
    render_header,
    render_stat_card,
)

apply_theme()

token = st.session_state.get("token")
user = st.session_state.get("user") or {}

if not token or user.get("role") != "admin":
    st.error("Administrator access required to view system settings.")
    st.stop()

render_header(
    "Settings & Infrastructure Health",
    "Monitor live service dependencies, active pipeline parameters, and security posture.",
    badge="ADMIN CONSOLE",
)

# Fetch Health Telemetry
try:
    health = get_system_health()
    overall_status = health.get("status", "unknown")
    deps = health.get("dependencies") or []
except Exception as exc:
    st.error(f"Failed to query backend health probe: {exc}")
    overall_status = "error"
    deps = []

# Status Row
h_col1, h_col2, h_col3 = st.columns(3)
with h_col1:
    render_stat_card(
        "Platform Status",
        overall_status.upper(),
        "FastAPI Backend Liveness Probe",
    )
with h_col2:
    render_stat_card(
        "Application Environment",
        health.get("env", "development").upper() if isinstance(health, dict) else "DEV",
        health.get("app", "ResolveAI") if isinstance(health, dict) else "ResolveAI",
    )
with h_col3:
    render_stat_card(
        "Healthy Dependencies",
        f"{sum(1 for d in deps if d.get('status') == 'ok')}/{len(deps)}",
        "PostgreSQL, Qdrant, Ollama",
    )

st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# ==============================================================================
# SECTION 1: LIVE DEPENDENCY STATUS PROBES
# ==============================================================================
st.markdown("### Infrastructure Dependency Probes")
st.caption("Real-time TCP & HTTP status checks against essential backing services.")

if not deps:
    st.info("Health telemetry unavailable.")
else:
    for dep in deps:
        name = dep.get("name", "Unknown").upper()
        status_val = dep.get("status", "unknown")
        detail = dep.get("detail")

        is_ok = status_val == "ok"
        border_color = "#ABF5D1" if is_ok else "#FFBDAD"
        bg_color = "#E3FCEF" if is_ok else "#FFEBE6"
        badge_class = "badge-resolved" if is_ok else "badge-escalated"

        st.markdown(
            f"""
            <div style="background:{bg_color}; border:1px solid {border_color}; border-radius:3px; padding:0.85rem 1.25rem; margin-bottom:0.75rem; display:flex; justify-content:space-between; align-items:center;">
                <div>
                    <strong style="color:#172B4D; font-size:0.95rem;">{name}</strong>
                    <div style="font-size:0.775rem; color:#5E6C84; margin-top:2px;">
                        {detail if detail else 'Responding within healthy latency bounds'}
                    </div>
                </div>
                <span class="badge {badge_class}">{status_val.upper()}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# ==============================================================================
# SECTION 2: ACTIVE PIPELINE & RETRIEVAL CONFIGURATION
# ==============================================================================
st.markdown("### Active RAG & Agent Settings")
st.caption("Parameters governing document chunking, hybrid retrieval fusion, and escalation triggers.")

with st.container(border=True):
    c_col1, c_col2 = st.columns(2)
    with c_col1:
        st.markdown(
            """
            **Retrieval Pipeline**
            - Mode: `Hybrid (Dense Vector + BM25 Lexical)`
            - Fusion Algorithm: `Reciprocal Rank Fusion (RRF k=60)`
            - Vector Database: `Qdrant (Cosine Distance, 768-dim)`
            - Minimum Similarity Threshold: `0.25`
            - Top-K Retrieved Chunks: `5`
            """
        )
    with c_col2:
        st.markdown(
            """
            **Models & Chunking**
            - Chat LLM: `qwen2.5:3b (Ollama)`
            - Embedder: `nomic-embed-text (Ollama)`
            - Chunk Size: `800 characters`
            - Chunk Overlap: `120 characters`
            - Upload Directory: `data/uploads`
            """
        )

    st.markdown("---")
    st.markdown(
        """
        **Automated Escalation Keywords**
        <br>
        <span class="badge badge-escalated" style="margin:2px;">delete workspace</span>
        <span class="badge badge-escalated" style="margin:2px;">delete account</span>
        <span class="badge badge-escalated" style="margin:2px;">disable mfa</span>
        <span class="badge badge-escalated" style="margin:2px;">chargeback</span>
        <span class="badge badge-escalated" style="margin:2px;">legal hold</span>
        <span class="badge badge-escalated" style="margin:2px;">ssn</span>
        <span class="badge badge-escalated" style="margin:2px;">social security</span>
        <br>
        <span style="font-size:0.75rem; color:#64748B; margin-top:6px; display:inline-block;">Inquiries containing these phrases are automatically intercepted by LangGraph guardrails and queued for Human Review.</span>
        """,
        unsafe_allow_html=True,
    )

st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# ==============================================================================
# SECTION 3: SECURITY & CREDENTIAL POSTURE
# ==============================================================================
st.markdown("### Security & Secrets Management Audit")
st.caption("Verifying credential isolation, rate limiting, and environment variable hygiene.")

with st.container(border=True):
    st.markdown(
        """
        <div style="font-size:0.875rem; color:#334155; line-height:1.6;">
            <strong>Environment & Credential Isolation Status:</strong>
            <ul>
                <li><strong>Local Tracking:</strong> The tracked <code>.env</code> file in this repository uses default development placeholders (<code>change-me-to-a-long-random-string</code>). No live production secrets or private API tokens are committed.</li>
                <li><strong>Production Deployment Recommendation:</strong> When promoting to staging or production, replace <code>JWT_SECRET</code>, <code>SERVICE_API_KEY</code>, and <code>POSTGRES_PASSWORD</code> with cryptographically random secrets from a secure vault (e.g., AWS Secrets Manager, HashiCorp Vault), and ensure <code>.env</code> is added to <code>.gitignore</code>.</li>
                <li><strong>Safe Draft Guardrail:</strong> Human escalation replies are stored safely in PostgreSQL. No automated external emails or destructive actions are dispatched without explicit staff authorization.</li>
                <li><strong>Rate Limiting:</strong> In-memory sliding window rate limiter active (60 req/min with burst allowance of 20).</li>
                <li><strong>JWT Protection:</strong> HS256 signed bearer tokens with 30-minute expiration. Role-based access control enforces customer vs admin data isolation on all endpoints.</li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )
