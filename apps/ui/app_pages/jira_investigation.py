"""Jira Integration & AI Investigation Workspace — Lookup, investigation, and safe review."""

from __future__ import annotations

import streamlit as st
from api_client import (
    ApiError,
    execute_jira_transition,
    get_jira_issue,
    get_jira_status,
    get_jira_transitions,
    investigate_jira_issue,
    publish_jira_comment,
)
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

if not token or user.get("role") != "admin":
    st.error("Access restricted: Administrator role required for Jira AI Investigation Layer.")
    st.stop()

render_header(
    "Jira AI Investigation Layer",
    "Investigate external Jira issues with hybrid RAG and historical precedents. Review and safely publish resolution drafts.",
    badge="JIRA CLOUD INTEGRATION",
)

# Governance & Safety Guardrails Notice
with st.expander("🛡️ Enterprise Governance & Safety Guardrails (Active)", expanded=False):
    st.markdown(
        """
        - **Atlassian Webhooks**: Inbound Jira webhooks (automatic triggering on issue creation in Jira) are not implemented; investigation is currently initiated on-demand by authorized staff to prevent runaway LLM costs and ensure human oversight.
        - **Bi-directional Status Synchronization**: The application deliberately refrains from auto-transitioning Jira issue statuses (e.g. Open -> Resolved) to satisfy safety and least-privilege requirements; state transitions remain under staff discretion.
        """
    )


# Fetch Jira integration status
try:
    status_info = get_jira_status(token)
except Exception as exc:
    status_info = {"configured": False, "connection_ok": False, "message": str(exc)}

is_configured = status_info.get("configured", False)
is_connected = status_info.get("connection_ok", False)

# State initialization
if "jira_issue_key" not in st.session_state:
    st.session_state.jira_issue_key = "DEMO-101"
if "current_jira_issue" not in st.session_state:
    st.session_state.current_jira_issue = None
if "current_investigation" not in st.session_state:
    st.session_state.current_investigation = None
if "draft_comment_text" not in st.session_state:
    st.session_state.draft_comment_text = ""

# ==============================================================================
# SECTION 1: CONNECTION STATUS & DEMO CONTROLS
# ==============================================================================
if is_configured and is_connected:
    st.markdown(
        f"""
        <div style="background:#F0FDF4; border:1px solid #BBF7D0; border-radius:8px; padding:0.85rem 1.25rem; margin-bottom:1.25rem; display:flex; justify-content:space-between; align-items:center;">
            <div>
                <strong style="color:#166534; font-size:0.95rem;">● Connected to Jira Cloud</strong>
                <div style="font-size:0.8rem; color:#15803D; margin-top:2px;">
                    Endpoint: <code>{status_info.get('base_url')}</code> · Project Key: <code>{status_info.get('project_key') or 'All Projects'}</code>
                </div>
            </div>
            <span class="badge badge-resolved">ACTIVE LINK</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
elif is_configured and not is_connected:
    st.markdown(
        f"""
        <div style="background:#FFF1F2; border:1px solid #FECACA; border-radius:8px; padding:0.85rem 1.25rem; margin-bottom:1.25rem;">
            <strong style="color:#9F1239; font-size:0.95rem;">⚠️ Jira Connection Error</strong>
            <div style="font-size:0.8rem; color:#881337; margin-top:2px;">
                {status_info.get('message')}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:1rem 1.25rem; margin-bottom:1.25rem;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <strong style="color:#1E293B; font-size:0.95rem;">ℹ️ Jira Cloud Not Configured (Demo Mode Active)</strong>
                <span class="badge badge-pending">LOCAL SANDBOX</span>
            </div>
            <div style="font-size:0.825rem; color:#64748B; margin-top:0.4rem; line-height:1.5;">
                To connect to live Jira Cloud, set <code>JIRA_BASE_URL</code>, <code>JIRA_EMAIL</code>, and <code>JIRA_API_TOKEN</code> in your <code>.env</code> file.<br>
                You can test and demonstrate the complete AI investigation workflow right now using built-in sandbox demo issues:
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Quick Demo Selectors
demo_c1, demo_c2, demo_c3 = st.columns([1, 1, 2])
with demo_c1:
    if st.button("Use Issue: DEMO-101", width="stretch"):
        st.session_state.jira_issue_key = "DEMO-101"
        st.session_state.current_investigation = None
        st.session_state.current_jira_issue = None
        st.rerun()
with demo_c2:
    if st.button("Use Issue: DEMO-102 (Escalation)", width="stretch"):
        st.session_state.jira_issue_key = "DEMO-102"
        st.session_state.current_investigation = None
        st.session_state.current_jira_issue = None
        st.rerun()

# ==============================================================================
# SECTION 2: ISSUE LOOKUP
# ==============================================================================
st.markdown("### Jira Issue Lookup")
with st.container(border=True):
    lookup_c1, lookup_c2 = st.columns([3, 1])
    with lookup_c1:
        issue_input = st.text_input(
            "Jira Issue Key",
            value=st.session_state.jira_issue_key,
            placeholder="e.g. SUP-101, PROJ-204, or DEMO-101",
        )
    with lookup_c2:
        st.markdown("<div style='margin-top: 1.7rem;'></div>", unsafe_allow_html=True)
        fetch_btn = st.button("🔍 Fetch Issue", type="primary", width="stretch")

if fetch_btn or (st.session_state.current_jira_issue is None and issue_input):
    with st.spinner(f"Retrieving issue '{issue_input.strip()}'…"):
        try:
            issue_data = get_jira_issue(issue_input.strip(), token)
            st.session_state.current_jira_issue = issue_data
            st.session_state.jira_issue_key = issue_input.strip().upper()
            st.session_state.current_investigation = None
        except ApiError as exc:
            st.error(f"Failed to fetch issue: {exc}")
            st.session_state.current_jira_issue = None

issue = st.session_state.current_jira_issue

# ==============================================================================
# SECTION 3: ISSUE DETAILS PREVIEW
# ==============================================================================
if issue:
    with st.container(border=True):
        p_col1, p_col2 = st.columns([3, 1])
        with p_col1:
            st.markdown(f"### [{issue['key']}] {issue['summary']}")
            st.markdown(
                f"""
                <span style="font-size:0.8rem; color:#64748B;">
                    Reporter: <strong>{issue.get('reporter')}</strong> ·
                    Assignee: <strong>{issue.get('assignee') or 'Unassigned'}</strong> ·
                    Created: {format_datetime(issue.get('created'))}
                </span>
                """,
                unsafe_allow_html=True,
            )
        with p_col2:
            st.markdown(
                f"""
                <div style="text-align:right;">
                    {get_status_badge_html(issue.get('status', 'Open'))}
                    <span style="margin-left:6px;">{get_priority_badge_html(issue.get('priority', 'Medium'))}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("#### Description")
        st.markdown(
            f"""
            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:6px; padding:0.85rem 1rem; font-size:0.875rem; color:#334155; line-height:1.5;">
                {issue.get('description') or '<em>No description provided.</em>'}
            </div>
            """,
            unsafe_allow_html=True,
        )

        comments = issue.get("comments") or []
        if comments:
            with st.expander(f"💬 Jira Comments ({len(comments)})", expanded=False):
                for c in comments:
                    st.markdown(f"**{c.get('author')}:** {c.get('body')}")
                    st.caption(f"Posted {format_datetime(c.get('created'))}")
                    st.divider()

        # Bi-directional Status Synchronization Section
        st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
        with st.expander("🔄 Bi-directional Status Synchronization", expanded=False):
            st.caption(
                "Synchronize issue workflow status directly between ResolveAI and Jira Cloud. "
                "The application deliberately refrains from auto-transitioning Jira issue statuses (e.g. Open -> Resolved) "
                "to satisfy safety and least-privilege requirements; state transitions remain under staff discretion."
            )

            try:
                available_transitions = get_jira_transitions(issue["key"], token)
            except Exception:
                available_transitions = []

            if not available_transitions:
                st.info("No available status transitions returned from Jira for this issue.")
            else:
                t_cols = st.columns([3, 1])
                with t_cols[0]:
                    transition_choices = {f"{t['name']} -> {t['to_status']}": t["name"] for t in available_transitions}
                    selected_trans_label = st.selectbox(
                        "Target Status Transition",
                        list(transition_choices.keys()),
                        label_visibility="collapsed",
                    )
                with t_cols[1]:
                    if st.button("Sync Status", width="stretch"):
                        target_trans_name = transition_choices[selected_trans_label]
                        with st.spinner(f"Transitioning '{issue['key']}' to '{target_trans_name}'…"):
                            try:
                                trans_res = execute_jira_transition(issue["key"], target_trans_name, token)
                                st.toast(trans_res.get("message", "Status synced!"), icon="🔄")
                                st.session_state.current_jira_issue = None
                                st.rerun()
                            except ApiError as exc:
                                st.error(f"Transition failed: {exc}")

    # Trigger Investigation Action
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)
    if st.button("🚀 Investigate with ResolveAI Agent", type="primary", icon=":material/psychology:"):
        with st.spinner("Executing LangGraph investigation workflow: loading context, hybrid RAG, and precedent analysis…"):
            try:
                inv_res = investigate_jira_issue(issue["key"], token)
                st.session_state.current_investigation = inv_res
                st.session_state.draft_comment_text = inv_res.get("draft_jira_comment", "")
                st.toast("Investigation completed!", icon="✅")
                st.rerun()
            except ApiError as exc:
                st.error(f"Investigation failed: {exc}")

# ==============================================================================
# SECTION 4: INVESTIGATION REPORT & SUPPORTING EVIDENCE
# ==============================================================================
inv = st.session_state.current_investigation

if inv:
    st.markdown("---")
    st.markdown("## 📋 ResolveAI Investigation Report")

    # Status & Confidence Metrics
    c_col1, c_col2, c_col3, c_col4 = st.columns(4)
    with c_col1:
        inv_status = inv.get("status", "conclusive")
        render_stat_card("Status", inv_status.upper(), "Investigation verdict")
    with c_col2:
        conf = inv.get("confidence_score", 0.0)
        render_stat_card("Confidence Score", f"{conf * 100:.1f}%", "Grounding certainty")
    with c_col3:
        render_stat_card("Category", inv.get("category", "General").upper(), "Classification")
    with c_col4:
        approval_txt = "REQUIRED" if inv.get("human_approval_required") else "OPTIONAL"
        render_stat_card("Human Approval", approval_txt, "Review boundary")

    st.caption(f"**Confidence Calculation Method:** {inv.get('confidence_method')}")
    st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

    # Escalation Callout if Escalated
    if inv.get("status") in ("escalated", "insufficient_evidence"):
        st.markdown(
            f"""
            <div class="escalation-callout">
                <div class="escalation-title">⚠️ Human Specialist Review Required</div>
                <div class="escalation-desc">
                    <strong>Findings:</strong> The investigation flagged missing information or safety boundaries.<br>
                    {'; '.join(inv.get('missing_information_or_risks') or ['Manual review advised before customer contact.'])}
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Core Investigation Sections
    with st.container(border=True):
        st.markdown("#### 1. Problem Summary")
        st.write(inv.get("problem_summary"))

        st.markdown("#### 2. Proposed Root Cause")
        root_cause = inv.get("proposed_root_cause", "")
        st.info(root_cause)

        st.markdown("#### 3. Recommended Resolution")
        st.markdown(inv.get("recommended_resolution", ""))

        # Evidence & KB Citations
        citations = inv.get("citations") or []
        if citations:
            with st.expander(f"📚 Supporting Knowledge Base Citations ({len(citations)})", expanded=True):
                for c in citations:
                    score = c.get("score", 0.0)
                    title = c.get("title") or c.get("filename") or "Knowledge Document"
                    st.markdown(
                        f"""
                        <div class="citation-item">
                            <div class="citation-header">
                                <span class="citation-title">[{c.get('index', 1)}] {title}</span>
                                <span class="citation-score">Relevance: {score:.3f}</span>
                            </div>
                            <div class="citation-snippet">{c.get('snippet', '')}</div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

        # Historical Precedents
        precedents = inv.get("similar_past_tickets") or []
        if precedents:
            with st.expander(f"🗂️ Historical Precedents in PostgreSQL ({len(precedents)})", expanded=False):
                for p in precedents:
                    st.markdown(f"• **Ticket #{p['id'][:8]}** ({p['status'].upper()}): {p['subject']}")

        # Investigation Steps performed
        steps = inv.get("investigation_steps") or []
        if steps:
            with st.expander("⚙️ Diagnostic Trace & Investigation Steps", expanded=False):
                for s in steps:
                    st.markdown(f"✓ {s}")

    # ==============================================================================
    # SECTION 5: DRAFT JIRA COMMENT & EXPLICIT PUBLISHING
    # ==============================================================================
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
    st.markdown("### Review & Publish to Jira")
    st.caption("Review the formatted resolution report below. Publishing will append this report as an official comment on the Jira issue.")

    with st.form("jira_publish_form"):
        edited_comment = st.text_area(
            "Draft Jira Comment",
            value=st.session_state.draft_comment_text,
            height=200,
        )

        confirm_publish = st.checkbox(
            "I have reviewed and verified this investigation report and explicitly authorize publishing it to Jira.",
            value=False,
        )

        publish_col1, publish_col2 = st.columns([1, 3])
        with publish_col1:
            publish_btn = st.form_submit_button("📢 Publish to Jira", type="primary")

    if publish_btn:
        if not confirm_publish:
            st.error("Please confirm authorization using the checkbox above before publishing to Jira.")
        elif not edited_comment.strip():
            st.error("Comment text cannot be empty.")
        else:
            with st.spinner("Publishing comment to Jira…"):
                try:
                    pub_res = publish_jira_comment(inv["issue_key"], edited_comment.strip(), token)
                    if pub_res.get("duplicate_prevented"):
                        st.info(f"Duplicate Guard: {pub_res.get('message')}")
                    else:
                        st.success(f"✅ {pub_res.get('message')} (Comment ID: `{pub_res.get('comment_id')}`)")
                except ApiError as exc:
                    st.error(f"Failed to publish comment: {exc}")
