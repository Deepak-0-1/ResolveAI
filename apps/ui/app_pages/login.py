"""Enterprise Login & Authentication Page."""

from __future__ import annotations

import streamlit as st
from api_client import ApiError, login_user
from theme import apply_theme

apply_theme()

st.markdown(
    """
    <div style="max-width: 480px; margin: 2rem auto 1.5rem auto; text-align: center;">
        <div style="background:#2563EB; color:white; font-weight:700; font-size:1.5rem; width:48px; height:48px; border-radius:12px; display:inline-flex; align-items:center; justify-content:center; margin-bottom:1rem;">R</div>
        <h1 style="font-size:1.75rem; font-weight:700; color:#0F172A; margin:0 0 0.5rem 0;">Welcome to ResolveAI</h1>
        <p style="color:#64748B; font-size:0.925rem; margin:0;">Enterprise AI-Powered Customer Resolution & Support Platform</p>
    </div>
    """,
    unsafe_allow_html=True,
)

col_left, col_center, col_right = st.columns([1, 2, 1])

with col_center:
    # State for quick demo selection
    if "login_email_prefill" not in st.session_state:
        st.session_state.login_email_prefill = ""

    demo_cols = st.columns(2)
    with demo_cols[0]:
        if st.button("Use Customer Account", width="stretch", icon=":material/person:"):
            st.session_state.login_email_prefill = "customer@resolveai.local"
            st.rerun()
    with demo_cols[1]:
        if st.button("Use Admin Account", width="stretch", icon=":material/admin_panel_settings:"):
            st.session_state.login_email_prefill = "admin@resolveai.local"
            st.rerun()

    with st.form("login_form", border=True):
        st.markdown("<h3 style='margin-top:0; font-size:1.1rem; color:#1E293B;'>Sign in to your account</h3>", unsafe_allow_html=True)
        email = st.text_input(
            "Work Email",
            value=st.session_state.login_email_prefill,
            placeholder="name@company.com",
        )
        password = st.text_input(
            "Password",
            type="password",
            placeholder="Enter your account password",
        )
        submitted = st.form_submit_button("Sign in", type="primary", width="stretch")

    if submitted:
        if not email or not password:
            st.error("Please provide both your email address and password.")
        else:
            with st.spinner("Authenticating credentials…"):
                try:
                    auth_data = login_user(email.strip(), password)
                    st.session_state.token = auth_data["token"]
                    st.session_state.user = auth_data["user"]
                    st.toast(f"Successfully signed in as {auth_data['user']['email']}", icon="✅")
                    st.rerun()
                except ApiError as exc:
                    st.error(f"Authentication failed: {exc}")
                except Exception as exc:
                    st.error(f"Unable to connect to the backend API: {exc}")

    st.markdown(
        """
        <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:8px; padding:1rem; margin-top:1.25rem; font-size:0.8rem; color:#64748B;">
            <strong style="color:#334155;">Demo Credentials (Local Environment)</strong><br>
            • Customer: <code>customer@resolveai.local</code> / <code>customer123!</code><br>
            • Admin: <code>admin@resolveai.local</code> / <code>admin123!</code><br>
            <span style="font-size:0.75rem; color:#94A3B8; margin-top:4px; display:inline-block;">Passwords are never prefilled into inputs. For production, rotate all default secrets in .env.</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
