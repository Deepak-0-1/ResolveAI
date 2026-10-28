"""Enterprise AI Support Assistant — Grounded RAG with citations, escalation, and feedback."""

from __future__ import annotations

import streamlit as st
from api_client import (
    ApiError,
    create_ticket,
    list_tickets,
    send_chat_message,
    send_feedback,
)
from theme import (
    apply_theme,
    get_priority_badge_html,
    get_status_badge_html,
    render_header,
)

apply_theme()

token = st.session_state.get("token")
user = st.session_state.get("user") or {}

if not token or not user:
    st.warning("Please sign in to chat with the AI Assistant.")
    st.stop()

is_admin = user.get("role") == "admin"

render_header(
    "AI Support Assistant",
    "Instant, document-grounded answers with citations. Complex or high-risk requests escalate safely to support staff.",
    badge="GROUNDED RAG",
)

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "linked_ticket_id" not in st.session_state:
    st.session_state.linked_ticket_id = None
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None

# Top Action Bar: Ticket Linking & Reset
top_col1, top_col2, top_col3 = st.columns([2, 1, 1])

with top_col1:
    # Optional link to existing ticket
    try:
        user_tickets = list_tickets(token)
        ticket_options = {"None (General Inquiry)": None}
        for ut in user_tickets:
            ticket_options[f"#{ut['id'][:8]} — {ut['subject'][:35]}"] = ut["id"]

        selected_ticket_label = st.selectbox(
            "Associate chat with ticket (optional):",
            list(ticket_options.keys()),
            index=0,
            label_visibility="collapsed",
        )
        st.session_state.linked_ticket_id = ticket_options[selected_ticket_label]
    except Exception:
        st.session_state.linked_ticket_id = None

with top_col2:
    show_diagnostics = st.toggle("Developer Diagnostics", value=is_admin)

with top_col3:
    if st.button("Clear Chat", icon=":material/refresh:", width="stretch"):
        st.session_state.chat_history = []
        st.session_state.pending_prompt = None
        st.rerun()

st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)

# Suggested Questions (Displayed when conversation is fresh)
SUGGESTED_QUESTIONS = [
    ("🔑 Password Reset", "How do I reset my NovaDesk account password?"),
    ("💳 Billing & Plans", "How can I update my billing method or view invoices?"),
    ("⚡ API Rate Limits", "What are the API rate limits and how does bursting work?"),
    ("🛡️ Security & Account", "What is the procedure to delete workspace data or disable MFA?"),
]

if not st.session_state.chat_history:
    st.markdown("<div style='font-size:0.875rem; font-weight:600; color:#475569; margin-bottom:0.5rem;'>Suggested Inquiries</div>", unsafe_allow_html=True)
    suggested_cols = st.columns(4)
    for idx, (label, question) in enumerate(SUGGESTED_QUESTIONS):
        with suggested_cols[idx]:
            if st.button(label, key=f"sugg_{idx}", width="stretch"):
                st.session_state.pending_prompt = question
                st.rerun()

# Render Conversation History
for turn_idx, turn in enumerate(st.session_state.chat_history):
    with st.chat_message("user"):
        st.markdown(turn["user"])

    with st.chat_message("assistant", avatar="🤖"):
        # Answer text
        st.markdown(turn["assistant"])

        # Escalation Notice
        if turn.get("status") == "escalated":
            esc_reason = turn.get("escalation_reason") or "Triggered high-risk keyword or low retrieval confidence."
            st.markdown(
                f"""
                <div class="escalation-callout">
                    <div class="escalation-title">⚠️ Escalation Triggered</div>
                    <div class="escalation-desc">
                        <strong>Reason:</strong> {esc_reason}<br>
                        This inquiry requires human verification and will not be automated without specialist review.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Citations Section
        citations = turn.get("citations") or []
        if citations:
            with st.expander(f"📚 Verified Sources & Citations ({len(citations)})", expanded=False):
                for cite in citations:
                    score = cite.get("score", 0.0)
                    title = cite.get("title") or cite.get("filename") or f"Doc #{cite.get('document_id', '')[:8]}"
                    st.markdown(
                        f"""
                        <div class="citation-item">
                            <div class="citation-header">
                                <span class="citation-title">[{cite.get('index', 1)}] {title}</span>
                                <span class="citation-score">Relevance: {score:.3f}</span>
                            </div>
                            <div class="citation-snippet">{cite.get('snippet', '')}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        # Developer Diagnostics Panel
        if show_diagnostics:
            trace = turn.get("trace") or []
            tools = turn.get("tools_used") or []
            st.markdown(
                f"""
                <div class="dev-panel">
                    <strong>⚙️ Diagnostics:</strong><br>
                    • Status: <code>{turn.get('status')}</code> | Category: <code>{turn.get('category')}</code> | Priority: <code>{turn.get('priority')}</code><br>
                    • Pipeline Trace: <code>{' → '.join(trace) if trace else 'direct'}</code><br>
                    • Tools Invocations: <code>{tools if tools else 'none'}</code><br>
                    • Top Retrieval Score: <code>{turn.get('top_score', 'N/A')}</code>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Feedback actions
        fb_cols = st.columns([1, 1, 4])
        with fb_cols[0]:
            if st.button("👍 Helpful", key=f"fb_up_{turn_idx}"):
                try:
                    send_feedback(1, token, comment="Helpful answer", ticket_id=turn.get("ticket_id"))
                    st.toast("Thank you for your feedback!", icon="✅")
                except ApiError as exc:
                    st.error(str(exc))
        with fb_cols[1]:
            if st.button("👎 Not helpful", key=f"fb_down_{turn_idx}"):
                try:
                    send_feedback(-1, token, comment="Not helpful", ticket_id=turn.get("ticket_id"))
                    st.toast("Feedback recorded for evaluation.", icon="📝")
                except ApiError as exc:
                    st.error(str(exc))

# Handle new prompt (either from pending suggested question or input bar)
prompt = st.chat_input("Ask a question about NovaDesk features, billing, or security…")
if st.session_state.pending_prompt:
    prompt = st.session_state.pending_prompt
    st.session_state.pending_prompt = None

if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        with st.spinner("Retrieving verified documents and synthesizing response…"):
            try:
                res = send_chat_message(
                    message=prompt,
                    token=token,
                    ticket_id=st.session_state.linked_ticket_id,
                )
            except ApiError as exc:
                st.error(f"Error from AI Assistant: {exc}")
                st.stop()
            except Exception as exc:
                st.error(f"Service communication error: {exc}")
                st.stop()

        st.markdown(res["answer"])

        if res.get("status") == "escalated":
            esc_reason = res.get("escalation_reason") or "Policy boundary or low confidence match."
            st.markdown(
                f"""
                <div class="escalation-callout">
                    <div class="escalation-title">⚠️ Escalation Triggered</div>
                    <div class="escalation-desc">
                        <strong>Reason:</strong> {esc_reason}<br>
                        This request has been routed to human support staff.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        citations = res.get("citations") or []
        if citations:
            with st.expander(f"📚 Verified Sources & Citations ({len(citations)})", expanded=True):
                for cite in citations:
                    score = cite.get("score", 0.0)
                    title = cite.get("title") or cite.get("filename") or f"Doc #{cite.get('document_id', '')[:8]}"
                    st.markdown(
                        f"""
                        <div class="citation-item">
                            <div class="citation-header">
                                <span class="citation-title">[{cite.get('index', 1)}] {title}</span>
                                <span class="citation-score">Relevance: {score:.3f}</span>
                            </div>
                            <div class="citation-snippet">{cite.get('snippet', '')}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        if show_diagnostics:
            trace = res.get("trace") or []
            tools = res.get("tools_used") or []
            st.markdown(
                f"""
                <div class="dev-panel">
                    <strong>⚙️ Diagnostics:</strong><br>
                    • Status: <code>{res.get('status')}</code> | Category: <code>{res.get('category')}</code> | Priority: <code>{res.get('priority')}</code><br>
                    • Pipeline Trace: <code>{' → '.join(trace) if trace else 'direct'}</code><br>
                    • Tools Invocations: <code>{tools if tools else 'none'}</code><br>
                    • Top Retrieval Score: <code>{res.get('top_score', 'N/A')}</code>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Record into session state
        st.session_state.chat_history.append(
            {
                "user": prompt,
                "assistant": res["answer"],
                "citations": citations,
                "status": res.get("status"),
                "escalation_reason": res.get("escalation_reason"),
                "category": res.get("category"),
                "priority": res.get("priority"),
                "trace": res.get("trace") or [],
                "tools_used": res.get("tools_used") or [],
                "top_score": res.get("top_score"),
                "ticket_id": res.get("ticket_id"),
            }
        )
