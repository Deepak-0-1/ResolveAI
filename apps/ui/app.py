"""ResolveAI Enterprise Support Platform — Streamlit Main Application."""

from __future__ import annotations

import streamlit as st
from theme import apply_theme

st.set_page_config(
    page_title="ResolveAI · AI Support Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

# Initialize session state variables
if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "active_ticket_id" not in st.session_state:
    st.session_state.active_ticket_id = None

# Define Pages
login_page = st.Page(
    "app_pages/login.py",
    title="Sign In",
    icon=":material/login:",
    default=True,
)

overview_page = st.Page(
    "app_pages/overview.py",
    title="Overview",
    icon=":material/dashboard:",
)

tickets_page = st.Page(
    "app_pages/tickets.py",
    title="Tickets",
    icon=":material/confirmation_number:",
)

chat_page = st.Page(
    "app_pages/chat.py",
    title="AI Assistant",
    icon=":material/smart_toy:",
)

human_review_page = st.Page(
    "app_pages/human_review.py",
    title="Human Review",
    icon=":material/rate_review:",
)

jira_page = st.Page(
    "app_pages/jira_investigation.py",
    title="Jira Investigation",
    icon=":material/integration_instructions:",
)

kb_page = st.Page(
    "app_pages/admin_kb.py",
    title="Knowledge Base",
    icon=":material/menu_book:",
)

eval_page = st.Page(
    "app_pages/admin_eval.py",
    title="AI Evaluation",
    icon=":material/analytics:",
)

settings_page = st.Page(
    "app_pages/admin_settings.py",
    title="Settings & Health",
    icon=":material/settings:",
)

user = st.session_state.user
token = st.session_state.token

if not token or not user:
    nav = st.navigation([login_page])
else:
    is_admin = user.get("role") == "admin"
    role_label = "Administrator" if is_admin else "Customer"
    user_name = user.get("full_name") or user.get("email", "User")

    # Render branded sidebar header
    with st.sidebar:
        st.markdown(
            f"""
            <div style="padding: 0.5rem 0 1rem 0;">
                <div style="display:flex; align-items:center; gap:0.5rem;">
                    <div style="background:#2563EB; color:white; font-weight:700; font-size:1.1rem; width:34px; height:34px; border-radius:8px; display:flex; align-items:center; justify-content:center;">R</div>
                    <div>
                        <div style="font-weight:700; font-size:1.1rem; color:#FFFFFF; letter-spacing:-0.02em;">ResolveAI</div>
                        <div style="font-size:0.75rem; color:#94A3B8;">Customer Resolution Engine</div>
                    </div>
                </div>
            </div>
            <div class="user-profile-badge">
                <div class="user-profile-name">
                    <span style="display:inline-block; width:8px; height:8px; border-radius:50%; background-color:#10B981;"></span>
                    {user_name}
                </div>
                <div class="user-profile-role">{role_label} · {user.get('email')}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Route based on authenticated user role
    if is_admin:
        nav = st.navigation(
            {
                "Support": [overview_page, tickets_page, chat_page, human_review_page, jira_page],
                "Administration": [kb_page, eval_page, settings_page],
            }
        )
    else:
        nav = st.navigation(
            {
                "Support": [overview_page, tickets_page, chat_page],
            }
        )

    with st.sidebar:
        st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)
        if st.button("Sign out", width="stretch", icon=":material/logout:"):
            st.session_state.token = None
            st.session_state.user = None
            st.session_state.chat_history = []
            st.session_state.active_ticket_id = None
            st.rerun()

nav.run()
