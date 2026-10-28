"""Overview Dashboard — Real-time telemetry, tickets, and AI resolution stats."""

from __future__ import annotations

import streamlit as st
from api_client import ApiError, get_analytics_overview, list_tickets
from theme import (
    apply_theme,
    format_datetime,
    get_priority_badge_html,
    get_status_badge_html,
    render_empty_state,
    render_header,
    render_stat_card,
)

apply_theme()

token = st.session_state.get("token")
user = st.session_state.get("user") or {}

if not token or not user:
    st.warning("Please sign in to view the dashboard.")
    st.stop()

is_admin = user.get("role") == "admin"

if is_admin:
    render_header(
        "Executive & Operations Dashboard",
        "Real-time support telemetry, ticket resolution pipeline, and RAG metrics.",
        badge="ADMIN CONSOLE",
    )
else:
    render_header(
        "Support Overview",
        f"Welcome back, {user.get('full_name') or user.get('email')}. Here is the current status of your tickets.",
        badge="CUSTOMER",
    )

try:
    with st.spinner("Fetching operational telemetry…"):
        overview = get_analytics_overview(token)
        tickets = list_tickets(token)
except ApiError as exc:
    st.error(f"Failed to load analytics: {exc}")
    st.stop()
except Exception as exc:
    st.error(f"Connection error: {exc}")
    st.stop()

# --- Key Metrics Row ---
col1, col2, col3, col4 = st.columns(4)

with col1:
    render_stat_card("Open Tickets", overview.get("open_tickets", 0), "Awaiting triage or reply")

with col2:
    escalated_count = overview.get("escalated_tickets", 0)
    render_stat_card(
        "Awaiting Review",
        escalated_count,
        "Escalated to human staff" if is_admin else "Under specialist review",
    )

with col3:
    render_stat_card("Resolved / Closed", overview.get("resolved_tickets", 0), "Successfully completed")

with col4:
    kb_stats = overview.get("kb_stats", {})
    if is_admin:
        render_stat_card(
            "Indexed KB Chunks",
            kb_stats.get("total_chunks", 0),
            f"{kb_stats.get('indexed_documents', 0)} documents active",
        )
    else:
        render_stat_card(
            "Total Requests",
            overview.get("total_tickets", 0),
            "Submitted all-time",
        )

st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# --- Secondary Section: AI & Operations Telemetry ---
if is_admin:
    m_col1, m_col2 = st.columns(2)

    with m_col1:
        st.markdown("### AI Resolution Performance")
        st.caption("Measured directly from system audit logs and chat agent sessions.")
        ai_res = overview.get("ai_resolutions_count", 0)
        ai_esc = overview.get("ai_escalations_count", 0)
        total_ai = ai_res + ai_esc
        rate_str = f"{(ai_res / total_ai * 100):.1f}%" if total_ai > 0 else "N/A"

        p_col1, p_col2, p_col3 = st.columns(3)
        with p_col1:
            render_stat_card("AI Direct Solves", ai_res, "Zero-escalation answers")
        with p_col2:
            render_stat_card("AI Escalations", ai_esc, "Handed off to agent")
        with p_col3:
            render_stat_card("Automation Rate", rate_str, "Self-service resolution")

        # Feedback stats
        fb_pos = overview.get("feedback_positive", 0)
        fb_neg = overview.get("feedback_negative", 0)
        st.markdown(
            f"""
            <div style="background:#FFFFFF; border:1px solid #E2E8F0; border-radius:8px; padding:0.85rem 1rem; margin-top:0.75rem; display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.85rem; color:#475569; font-weight:500;">Customer Feedback Ratings</span>
                <div>
                    <span style="color:#059669; font-weight:600; margin-right:1rem;">👍 {fb_pos} Helpful</span>
                    <span style="color:#DC2626; font-weight:600;">👎 {fb_neg} Not Helpful</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m_col2:
        st.markdown("### Ticket Priority & Status")
        st.caption("Current workload distribution across severity tiers.")
        prio_dist = overview.get("priority_distribution", {})
        status_dist = overview.get("status_distribution", {})

        prio_cols = st.columns(4)
        with prio_cols[0]:
            render_stat_card("Critical", prio_dist.get("critical", 0), "P1")
        with prio_cols[1]:
            render_stat_card("High", prio_dist.get("high", 0), "P2")
        with prio_cols[2]:
            render_stat_card("Medium", prio_dist.get("medium", 0), "P3")
        with prio_cols[3]:
            render_stat_card("Low", prio_dist.get("low", 0), "P4")

        # Knowledge base status bar
        st.markdown(
            f"""
            <div style="background:#FFFFFF; border:1px solid #DFE1E6; border-radius:4px; padding:0.85rem 1rem; margin-top:0.75rem; display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:0.85rem; color:#5E6C84; font-weight:600;">Knowledge Base Ingestion Status</span>
                <div>
                    <span style="color:#0052CC; font-weight:600; margin-right:1rem;">📚 {kb_stats.get('total_documents', 0)} Total</span>
                    <span style="color:#006644; font-weight:600; margin-right:1rem;">✅ {kb_stats.get('indexed_documents', 0)} Indexed</span>
                    <span style="color:#BF2600; font-weight:600;">⚠️ {kb_stats.get('failed_documents', 0)} Failed</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# --- Lower Section: Recent Escalation Activity & Recent Tickets ---
row_col1, row_col2 = st.columns([1, 1] if is_admin else [2, 1])

with row_col1:
    st.markdown("### Recent Support Tickets")
    st.caption("Latest recorded tickets and triage statuses.")

    if not tickets:
        render_empty_state("No Tickets Yet", "Tickets submitted via the portal will appear here.")
    else:
        for t in tickets[:6]:
            with st.container(border=True):
                top_cols = st.columns([3, 1])
                with top_cols[0]:
                    st.markdown(f"**{t['subject']}**")
                    st.caption(f"ID: `{t['id'][:8]}…` · Category: {t.get('category') or 'Unassigned'}")
                with top_cols[1]:
                    st.markdown(
                        f"""
                        <div style="text-align:right;">
                            {get_status_badge_html(t['status'])}<br>
                            <span style="margin-top:4px; display:inline-block;">{get_priority_badge_html(t['priority'])}</span>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                st.caption(f"Created {format_datetime(t.get('created_at'))}")

with row_col2:
    if is_admin:
        st.markdown("### Recent Escalation Activity")
        st.caption("Automated handoffs triggered by risk keywords or low retrieval confidence.")

        escalations = overview.get("recent_escalations", [])
        if not escalations:
            render_empty_state(
                "No Escalations Pending",
                "All recent customer inquiries were resolved or within normal confidence bounds.",
            )
        else:
            for esc in escalations[:5]:
                with st.container(border=True):
                    st.markdown(
                        f"""
                        <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                            <div>
                                <span style="font-weight:600; color:#172B4D; font-size:0.9rem;">{esc['subject']}</span><br>
                                <span style="font-size:0.75rem; color:#5E6C84;">Ticket: <code>{esc['ticket_id'][:8]}…</code></span>
                            </div>
                            {get_priority_badge_html(esc['priority'])}
                        </div>
                        <div style="background:#FFEBE6; border:1px solid #FFBDAD; border-radius:3px; padding:0.4rem 0.6rem; margin-top:0.4rem; font-size:0.8rem; color:#BF2600;">
                            <strong>Reason:</strong> {esc['reason']}
                        </div>
                        <div style="font-size:0.75rem; color:#6B778C; margin-top:0.35rem;">
                            Escalated at {format_datetime(esc.get('timestamp'))}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
    else:
        st.markdown("### Need Help?")
        st.caption("Access our grounded AI assistant or create a new support ticket.")
        with st.container(border=True):
            st.markdown(
                """
                **AI Support Assistant**
                Get instant answers backed by official knowledge base documents and verified citations.
                """
            )
            if st.button("Open AI Assistant", width="stretch", type="primary", icon=":material/smart_toy:"):
                st.switch_page("app_pages/chat.py")

        with st.container(border=True):
            st.markdown(
                """
                **Submit a Ticket**
                Need personalized help from our engineering or billing team? Open a tracked support ticket.
                """
            )
            if st.button("New Support Ticket", width="stretch", icon=":material/add:"):
                st.switch_page("app_pages/tickets.py")
