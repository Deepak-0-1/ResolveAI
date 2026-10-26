import streamlit as st
from api_client import ApiError, request

st.title("Escalations & drafts")
st.caption("Review escalated tickets and store draft replies (never auto-sent).")

token = st.session_state.get("token")
user = st.session_state.get("user") or {}
if not token or user.get("role") != "admin":
    st.error("Admin access required.")
    st.stop()

try:
    tickets = request(
        "GET",
        "/tickets",
        token=token,
        params={"status": "escalated"},
    )
except ApiError as exc:
    st.error(str(exc))
    st.stop()

if not tickets:
    st.info("No escalated tickets right now.")
else:
    for ticket in tickets:
        with st.expander(f"{ticket['subject']} · {ticket['id']}"):
            st.write(ticket)
            try:
                detail = request("GET", f"/tickets/{ticket['id']}", token=token)
                for message in detail.get("messages") or []:
                    st.markdown(f"**{message['role']}:** {message['content']}")
            except ApiError as exc:
                st.error(str(exc))

            draft = st.text_area("Draft reply", key=f"draft_{ticket['id']}")
            if st.button("Save draft", key=f"save_{ticket['id']}"):
                if not draft.strip():
                    st.warning("Draft body is empty.")
                else:
                    try:
                        result = request(
                            "POST",
                            f"/tickets/{ticket['id']}/draft",
                            token=token,
                            json={"body": draft},
                        )
                        st.success(result.get("note") or "Draft saved")
                        st.code(result.get("draft_preview") or "", language=None)
                    except ApiError as exc:
                        st.error(str(exc))

st.divider()
st.subheader("All tickets")
try:
    all_tickets = request("GET", "/tickets", token=token)
    st.dataframe(all_tickets, width="stretch")
except ApiError as exc:
    st.error(str(exc))
