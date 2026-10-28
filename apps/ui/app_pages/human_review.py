"""Human Review & Escalation Queue — Staff review, draft editing, and safe approval."""

from __future__ import annotations

import streamlit as st
from api_client import (
    ApiError,
    add_ticket_message,
    get_ticket_detail,
    list_tickets,
    save_ticket_draft,
    update_ticket,
)
from theme import (
    apply_theme,
    format_datetime,
    get_priority_badge_html,
    get_status_badge_html,
    render_empty_state,
    render_header,
)

apply_theme()

token = st.session_state.get("token")
user = st.session_state.get("user") or {}

if not token or user.get("role") != "admin":
    st.error("Access restricted: Administrator role required to access the Human Review Queue.")
    st.stop()

render_header(
    "Human Review & Escalation Queue",
    "Inspect tickets flagged by AI safety policies or low retrieval scores. Safely draft, edit, and approve resolutions.",
    badge="STAFF REVIEW QUEUE",
)

# Fetch all escalated tickets
try:
    escalated_tickets = list_tickets(token, status="escalated")
except ApiError as exc:
    st.error(f"Failed to fetch escalated tickets: {exc}")
    st.stop()

if "selected_review_ticket_id" not in st.session_state:
    st.session_state.selected_review_ticket_id = escalated_tickets[0]["id"] if escalated_tickets else None

# Queue Status Metric Header
st.markdown(
    f"""
    <div style="background:#FFFFFF; border:1px solid #DFE1E6; border-radius:4px; padding:0.85rem 1.25rem; margin-bottom:1.25rem; display:flex; justify-content:space-between; align-items:center;">
        <div>
            <span style="font-size:0.9rem; font-weight:600; color:#172B4D;">Pending Specialist Review</span>
            <span style="font-size:0.8rem; color:#5E6C84; margin-left:0.5rem;">({len(escalated_tickets)} ticket{'s' if len(escalated_tickets) != 1 else ''} in queue)</span>
        </div>
        <span class="badge badge-escalated">{len(escalated_tickets)} AWAITING ACTION</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if not escalated_tickets:
    render_empty_state(
        "Human Review Queue is Clear",
        "There are currently no tickets awaiting specialist review or escalation approval.",
    )
else:
    # Selector for tickets in the queue
    options_map = {
        f"#{t['id'][:8]} — {t['subject'][:45]} ({t['priority'].upper()})": t["id"]
        for t in escalated_tickets
    }

    selected_label = st.selectbox(
        "Select ticket from queue to review:",
        list(options_map.keys()),
        index=0,
        label_visibility="visible",
    )
    current_ticket_id = options_map[selected_label]

    # Fetch full ticket detail
    try:
        detail = get_ticket_detail(current_ticket_id, token)
    except ApiError as exc:
        st.error(f"Failed to load ticket detail: {exc}")
        st.stop()

    # Ticket Metadata & Escalation Header
    with st.container(border=True):
        m_col1, m_col2 = st.columns([3, 1])
        with m_col1:
            st.markdown(f"### {detail['subject']}")
            st.markdown(
                f"""
                <span style="font-size:0.8rem; color:#64748B;">
                    Ticket ID: <code>{detail['id']}</code> ·
                    Category: <strong>{detail.get('category') or 'Pending Classification'}</strong> ·
                    Submitted: {format_datetime(detail.get('created_at'))}
                </span>
                """,
                unsafe_allow_html=True,
            )
        with m_col2:
            st.markdown(
                f"""
                <div style="text-align:right;">
                    {get_status_badge_html(detail['status'])}
                    <span style="margin-left:6px;">{get_priority_badge_html(detail['priority'])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        # Visible Escalation Warning
        st.markdown(
            """
            <div class="escalation-callout">
                <div class="escalation-title">⚠️ Escalation Policy Triggered</div>
                <div class="escalation-desc">
                    The AI support agent paused automated reply due to sensitive safety boundaries or retrieval certainty below threshold.
                    External messages are withheld until explicit human approval.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Conversation History & Context
    st.markdown("#### Conversation & Context")
    messages = detail.get("messages") or []

    # Find existing draft if present
    existing_draft_text = ""
    for m in messages:
        content = m.get("content", "")
        if content.startswith("[DRAFT]"):
            existing_draft_text = content.replace("[DRAFT]", "").strip()

    with st.container(border=True):
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            time_str = format_datetime(m.get("created_at"))

            if role == "user":
                with st.chat_message("user"):
                    st.markdown(f"**Customer:** {content}")
                    st.caption(f"Received at {time_str}")
            elif role in ("agent", "assistant"):
                is_draft = content.startswith("[DRAFT]")
                avatar = "✍️" if is_draft else "🧑‍💼"
                with st.chat_message("assistant", avatar=avatar):
                    badge_title = "Stored Draft Response" if is_draft else "Official Agent Response"
                    st.markdown(f"**{badge_title}:** {content}")
                    st.caption(f"Recorded at {time_str}")

    # Resolution & Draft Workspace
    st.markdown("#### Human Review Resolution Workspace")
    st.caption("Draft your response below. You can save as draft or explicitly approve to post the official resolution.")

    # Form for editing draft and approving
    with st.form(f"review_action_form_{current_ticket_id}"):
        draft_input = st.text_area(
            "Agent Response Body",
            value=existing_draft_text,
            placeholder="Type or revise the resolution message for the customer…",
            height=140,
        )

        st.markdown(
            "<span style='font-size:0.75rem; color:#64748B;'>Safe Behavior: Storing a draft persists it to the database for team review without notifying external systems. Explicit approval publishes it to the ticket conversation.</span>",
            unsafe_allow_html=True,
        )

        b_cols = st.columns([1, 1, 1, 1])
        with b_cols[0]:
            save_btn = st.form_submit_button("💾 Save Draft Only")
        with b_cols[1]:
            approve_btn = st.form_submit_button("✅ Approve & Resolve", type="primary")
        with b_cols[2]:
            approve_pending_btn = st.form_submit_button("📨 Approve & Await Reply")
        with b_cols[3]:
            close_btn = st.form_submit_button("🔒 Close Ticket")

    if save_btn:
        if not draft_input.strip():
            st.warning("Draft message cannot be empty.")
        else:
            try:
                res = save_ticket_draft(current_ticket_id, draft_input.strip(), token)
                st.success(res.get("note") or "Draft saved to ticket record.")
                st.rerun()
            except ApiError as exc:
                st.error(f"Failed to save draft: {exc}")

    if approve_btn:
        if not draft_input.strip():
            st.error("Please enter a response body before approving.")
        else:
            try:
                # 1. Post approved message as agent
                add_ticket_message(
                    ticket_id=current_ticket_id,
                    content=draft_input.strip(),
                    token=token,
                    role="agent",
                )
                # 2. Update status to resolved
                update_ticket(current_ticket_id, token, status="resolved")
                st.toast("Resolution approved and ticket marked Resolved!", icon="✅")
                st.rerun()
            except ApiError as exc:
                st.error(f"Failed to approve resolution: {exc}")

    if approve_pending_btn:
        if not draft_input.strip():
            st.error("Please enter a response body before approving.")
        else:
            try:
                add_ticket_message(
                    ticket_id=current_ticket_id,
                    content=draft_input.strip(),
                    token=token,
                    role="agent",
                )
                update_ticket(current_ticket_id, token, status="pending")
                st.toast("Reply sent and ticket set to Pending Customer Reply.", icon="📨")
                st.rerun()
            except ApiError as exc:
                st.error(f"Failed to update ticket: {exc}")

    if close_btn:
        try:
            update_ticket(current_ticket_id, token, status="closed")
            st.toast("Ticket closed.", icon="🔒")
            st.rerun()
        except ApiError as exc:
            st.error(f"Failed to close ticket: {exc}")

st.markdown("<div style='margin-top: 2rem;'></div>", unsafe_allow_html=True)
st.markdown("### All Historical Tickets & Escalations")
try:
    all_tickets = list_tickets(token)
    st.dataframe(
        [
            {
                "ID": t["id"][:8] + "…",
                "Subject": t["subject"],
                "Status": t["status"].upper(),
                "Priority": t["priority"].upper(),
                "Category": t.get("category") or "—",
                "Created": format_datetime(t.get("created_at")),
            }
            for t in all_tickets
        ],
        width="stretch",
    )
except ApiError as exc:
    st.error(str(exc))
