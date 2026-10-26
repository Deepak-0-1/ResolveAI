"""ResolveAI Streamlit UI — customer + admin roles."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="ResolveAI",
    page_icon=":material/support_agent:",
    layout="wide",
)

if "token" not in st.session_state:
    st.session_state.token = None
if "user" not in st.session_state:
    st.session_state.user = None

login_page = st.Page("app_pages/login.py", title="Sign in", icon=":material/login:")
chat_page = st.Page("app_pages/chat.py", title="Chat", icon=":material/chat:")
tickets_page = st.Page(
    "app_pages/tickets.py",
    title="Tickets",
    icon=":material/confirmation_number:",
)
kb_page = st.Page(
    "app_pages/admin_kb.py",
    title="Knowledge base",
    icon=":material/menu_book:",
)
esc_page = st.Page(
    "app_pages/admin_escalations.py",
    title="Escalations",
    icon=":material/priority_high:",
)

user = st.session_state.user
if not st.session_state.token or not user:
    nav = st.navigation([login_page])
else:
    with st.sidebar:
        st.markdown(f"**{user.get('full_name') or user.get('email')}**")
        st.caption(user.get("role", ""))
        if st.button("Sign out", width="stretch"):
            st.session_state.token = None
            st.session_state.user = None
            st.session_state.chat_history = []
            st.rerun()

    if user.get("role") == "admin":
        nav = st.navigation(
            {
                "Support": [chat_page, tickets_page],
                "Admin": [kb_page, esc_page],
            }
        )
    else:
        nav = st.navigation([chat_page, tickets_page])

nav.run()
