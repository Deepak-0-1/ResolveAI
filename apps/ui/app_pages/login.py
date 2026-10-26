import streamlit as st
from api_client import ApiError, request

st.title("Sign in")
st.caption("Use seed accounts or a registered customer email.")

with st.form("login_form"):
    email = st.text_input("Email", value="customer@resolveai.local")
    password = st.text_input("Password", type="password", value="customer123!")
    submitted = st.form_submit_button("Sign in", type="primary", width="stretch")

if submitted:
    try:
        token_payload = request(
            "POST",
            "/auth/login",
            json={"email": email, "password": password},
        )
        token = token_payload["access_token"]
        me = request("GET", "/auth/me", token=token)
        st.session_state.token = token
        st.session_state.user = me
        st.success(f"Signed in as {me['email']} ({me['role']})")
        st.rerun()
    except ApiError as exc:
        st.error(f"Login failed: {exc}")

st.divider()
st.markdown(
    """
**Demo accounts**
- `customer@resolveai.local` / `customer123!`
- `admin@resolveai.local` / `admin123!`
"""
)
