"""Ticket Management Workspace — Search, triage, conversation history, and resolution."""

from __future__ import annotations

import streamlit as st
from api_client import (
    ApiError,
    add_ticket_message,
    create_ticket,
    get_ticket_detail,
    list_tickets,
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

if not token or not user:
    st.warning("Please sign in to access support tickets.")
    st.stop()

is_admin = user.get("role") == "admin"

render_header(
    "Support Tickets Workspace",
    "Track, triage, and collaborate on customer inquiries and resolutions."
    if is_admin
    else "View and manage your support requests with our support team.",
    badge="ADMIN VIEW" if is_admin else "CUSTOMER VIEW",
)

# Manage selected ticket state
if "selected_ticket_id" not in st.session_state:
    st.session_state.selected_ticket_id = None
if "show_create_form" not in st.session_state:
    st.session_state.show_create_form = False

# --- TICKET CREATION FORM (Expandable / Toggleable) ---
create_col, _ = st.columns([2, 3])
with create_col:
    button_label = "✕ Cancel Ticket Creation" if st.session_state.show_create_form else "+ Create New Support Ticket"
    if st.button(button_label, type="primary" if not st.session_state.show_create_form else "secondary"):
        st.session_state.show_create_form = not st.session_state.show_create_form
        st.rerun()

if st.session_state.show_create_form:
    with st.container(border=True):
        st.markdown("#### Submit a New Support Ticket")
        with st.form("create_ticket_form", clear_on_submit=True):
            f_col1, f_col2 = st.columns([3, 1])
            with f_col1:
                subject = st.text_input("Subject", placeholder="Brief description of the inquiry or issue")
            with f_col2:
                category = st.selectbox(
                    "Category",
                    ["General", "Billing & Subscriptions", "Account & Authentication", "API & Webhooks", "Data Privacy & Security"],
                )

            body = st.text_area(
                "Detailed Description",
                placeholder="Provide complete steps to reproduce, error messages, or questions…",
                height=120,
            )

            p_col1, p_col2 = st.columns(2)
            with p_col1:
                priority = st.selectbox("Priority", ["low", "medium", "high", "critical"], index=1)
            with p_col2:
                urgency = st.selectbox("Urgency", ["low", "medium", "high"], index=1)

            submit_new = st.form_submit_button("Submit Ticket", type="primary")

        if submit_new:
            if not subject.strip() or not body.strip():
                st.error("Both subject and description are required.")
            else:
                try:
                    new_ticket = create_ticket(
                        token=token,
                        subject=subject.strip(),
                        body=body.strip(),
                        category=category,
                        priority=priority,
                        urgency=urgency,
                    )
                    st.success(f"Ticket #{new_ticket['id'][:8]} created successfully!")
                    st.session_state.show_create_form = False
                    st.session_state.selected_ticket_id = new_ticket["id"]
                    st.rerun()
                except ApiError as exc:
                    st.error(f"Failed to create ticket: {exc}")

st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

# ==============================================================================
# DEDICATED TICKET DETAIL VIEW
# ==============================================================================
if st.session_state.selected_ticket_id:
    ticket_id = st.session_state.selected_ticket_id
    if st.button("← Back to All Tickets", icon=":material/arrow_back:"):
        st.session_state.selected_ticket_id = None
        st.rerun()

    try:
        detail = get_ticket_detail(ticket_id, token)
    except ApiError as exc:
        st.error(f"Failed to load ticket details: {exc}")
        st.stop()

    # Ticket Header Card
    with st.container(border=True):
        h_col1, h_col2 = st.columns([3, 1])
        with h_col1:
            st.markdown(f"### {detail['subject']}")
            st.markdown(
                f"""
                <span style="font-size:0.8rem; color:#64748B;">
                    Ticket ID: <code>{detail['id']}</code> · Category: <strong>{detail.get('category') or 'Unclassified'}</strong> ·
                    Created: {format_datetime(detail.get('created_at'))} ·
                    Last Updated: {format_datetime(detail.get('updated_at'))}
                </span>
                """,
                unsafe_allow_html=True,
            )
        with h_col2:
            st.markdown(
                f"""
                <div style="text-align:right;">
                    {get_status_badge_html(detail['status'])}
                    <span style="margin-left:6px;">{get_priority_badge_html(detail['priority'])}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Escalation Alert Notice if Escalated
    if detail["status"] == "escalated":
        st.markdown(
            """
            <div class="escalation-callout">
                <div class="escalation-title">⚠️ Escalated for Human Review</div>
                <div class="escalation-desc">
                    This ticket triggered sensitive safety policies, risk keywords, or low retrieval certainty.
                    An expert human support specialist is currently handling it.
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Staff Triage Controls (Admins only)
    if is_admin:
        with st.expander("🛠️ Staff Triage & Metadata Editor (Admin)", expanded=False):
            st.caption("Review and correct automated classifications or update ticket lifecycle status.")
            with st.form(f"triage_form_{ticket_id}"):
                t_col1, t_col2, t_col3, t_col4 = st.columns(4)
                with t_col1:
                    new_status = st.selectbox(
                        "Status",
                        ["open", "pending", "escalated", "resolved", "closed"],
                        index=["open", "pending", "escalated", "resolved", "closed"].index(detail["status"])
                        if detail["status"] in ["open", "pending", "escalated", "resolved", "closed"]
                        else 0,
                    )
                with t_col2:
                    new_cat = st.text_input("Category", value=detail.get("category") or "")
                with t_col3:
                    new_priority = st.selectbox(
                        "Priority",
                        ["low", "medium", "high", "critical"],
                        index=["low", "medium", "high", "critical"].index(detail["priority"])
                        if detail["priority"] in ["low", "medium", "high", "critical"]
                        else 1,
                    )
                with t_col4:
                    new_urgency = st.selectbox(
                        "Urgency",
                        ["low", "medium", "high"],
                        index=["low", "medium", "high"].index(detail["urgency"])
                        if detail["urgency"] in ["low", "medium", "high"]
                        else 1,
                    )

                save_triage = st.form_submit_button("Update Triage Metadata", type="primary")

            if save_triage:
                try:
                    update_ticket(
                        ticket_id=ticket_id,
                        token=token,
                        status=new_status,
                        category=new_cat.strip() or None,
                        priority=new_priority,
                        urgency=new_urgency,
                    )
                    st.success("Triage metadata updated successfully.")
                    st.rerun()
                except ApiError as exc:
                    st.error(f"Failed to update triage: {exc}")

    # Conversation History Timeline
    st.markdown("#### Conversation History")
    messages = detail.get("messages") or []

    if not messages:
        render_empty_state("No Messages", "This ticket does not have any recorded messages yet.")
    else:
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            created = format_datetime(m.get("created_at"))

            if role == "user":
                with st.chat_message("user"):
                    st.markdown(f"**Customer** · <span style='font-size:0.75rem; color:#94A3B8;'>{created}</span>", unsafe_allow_html=True)
                    st.markdown(content)
            elif role in ("agent", "assistant"):
                is_draft = content.startswith("[DRAFT]")
                avatar = "🤖" if (role == "assistant" and not is_draft) else ("✍️" if is_draft else "🧑‍💼")
                with st.chat_message("assistant", avatar=avatar):
                    badge_label = "AI Assistant (Automated)" if role == "assistant" and not is_draft else ("Staff Draft" if is_draft else "Human Support Agent")
                    st.markdown(f"**{badge_label}** · <span style='font-size:0.75rem; color:#94A3B8;'>{created}</span>", unsafe_allow_html=True)
                    st.markdown(content)
            else:
                with st.chat_message("system"):
                    st.markdown(f"**System** · <span style='font-size:0.75rem; color:#94A3B8;'>{created}</span>", unsafe_allow_html=True)
                    st.markdown(content)

    # Reply Box
    st.markdown("#### Add Reply")
    with st.form(f"reply_form_{ticket_id}"):
        reply_content = st.text_area(
            "Message Content",
            placeholder="Type your response here…",
            height=100,
        )
        r_cols = st.columns([1, 1, 2])
        with r_cols[0]:
            submit_reply = st.form_submit_button("Send Reply", type="primary")
        with r_cols[1]:
            if not is_admin and detail["status"] != "closed":
                close_ticket = st.form_submit_button("Close Ticket")
            else:
                close_ticket = False

    if submit_reply:
        if not reply_content.strip():
            st.error("Reply message cannot be empty.")
        else:
            try:
                add_ticket_message(
                    ticket_id=ticket_id,
                    content=reply_content.strip(),
                    token=token,
                    role="agent" if is_admin else "user",
                )
                st.success("Reply posted.")
                st.rerun()
            except ApiError as exc:
                st.error(f"Failed to post reply: {exc}")

    if close_ticket:
        try:
            update_ticket(ticket_id=ticket_id, token=token, status="closed")
            st.success("Ticket closed.")
            st.rerun()
        except ApiError as exc:
            st.error(f"Failed to close ticket: {exc}")

    st.stop()


# ==============================================================================
# TICKET LIST WORKSPACE VIEW
# ==============================================================================
# Filter & Search Controls
filter_col1, filter_col2, filter_col3 = st.columns([2, 1, 1])

with filter_col1:
    search_query = st.text_input(
        "Search Tickets",
        placeholder="Search by subject, category, or ticket ID…",
        label_visibility="collapsed",
    )

with filter_col2:
    status_filter = st.selectbox(
        "Filter by Status",
        ["All Statuses", "open", "pending", "escalated", "resolved", "closed"],
        label_visibility="collapsed",
    )

with filter_col3:
    priority_filter = st.selectbox(
        "Filter by Priority",
        ["All Priorities", "critical", "high", "medium", "low"],
        label_visibility="collapsed",
    )

# Fetch Tickets
try:
    api_status = None if status_filter == "All Statuses" else status_filter
    all_tickets = list_tickets(token, status=api_status)
except ApiError as exc:
    st.error(f"Failed to fetch tickets: {exc}")
    st.stop()

# Client-side filtering for search & priority
filtered_tickets = all_tickets
if search_query.strip():
    q = search_query.strip().lower()
    filtered_tickets = [
        t
        for t in filtered_tickets
        if q in t["subject"].lower()
        or q in t["id"].lower()
        or (t.get("category") and q in t["category"].lower())
    ]

if priority_filter != "All Priorities":
    filtered_tickets = [t for t in filtered_tickets if t["priority"].lower() == priority_filter.lower()]

# Results Summary
st.markdown(
    f"<span style='font-size:0.85rem; color:#64748B;'>Showing <strong>{len(filtered_tickets)}</strong> of {len(all_tickets)} tickets</span>",
    unsafe_allow_html=True,
)
st.markdown("<div style='margin-top: 0.5rem;'></div>", unsafe_allow_html=True)

if not filtered_tickets:
    render_empty_state(
        "No Matching Tickets Found",
        "Try adjusting your search criteria or create a new support ticket above.",
    )
else:
    for t in filtered_tickets:
        with st.container(border=True):
            r_col1, r_col2, r_col3 = st.columns([3, 1, 1])
            with r_col1:
                st.markdown(f"**{t['subject']}**")
                st.markdown(
                    f"""
                    <span style="font-size:0.775rem; color:#64748B;">
                        ID: <code>{t['id'][:8]}…</code> ·
                        Category: <strong>{t.get('category') or 'General'}</strong> ·
                        Created: {format_datetime(t.get('created_at'))}
                    </span>
                    """,
                    unsafe_allow_html=True,
                )
            with r_col2:
                st.markdown(
                    f"""
                    <div>
                        {get_status_badge_html(t['status'])}<br>
                        <span style="margin-top:4px; display:inline-block;">{get_priority_badge_html(t['priority'])}</span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            with r_col3:
                st.markdown("<div style='margin-top: 0.25rem;'></div>", unsafe_allow_html=True)
                if st.button("View Conversation →", key=f"btn_view_{t['id']}", width="stretch"):
                    st.session_state.selected_ticket_id = t["id"]
                    st.rerun()
