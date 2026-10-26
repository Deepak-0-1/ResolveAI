import streamlit as st
from api_client import ApiError, request

st.title("My tickets")

token = st.session_state.get("token")
if not token:
    st.warning("Please sign in first.")
    st.stop()

with st.form("new_ticket"):
    st.subheader("Create ticket")
    subject = st.text_input("Subject")
    body = st.text_area("Description")
    submitted = st.form_submit_button("Create", type="primary")
if submitted:
    if not subject or not body:
        st.error("Subject and description are required.")
    else:
        try:
            ticket = request(
                "POST",
                "/tickets",
                token=token,
                json={"subject": subject, "body": body},
            )
            st.success(f"Created ticket {ticket['id']}")
            st.rerun()
        except ApiError as exc:
            st.error(str(exc))

st.divider()
try:
    tickets = request("GET", "/tickets", token=token)
except ApiError as exc:
    st.error(str(exc))
    st.stop()

if not tickets:
    st.info("No tickets yet.")
else:
    for ticket in tickets:
        with st.expander(f"{ticket['subject']} · {ticket['status']} · {ticket['id'][:8]}…"):
            st.write(
                {
                    "id": ticket["id"],
                    "status": ticket["status"],
                    "category": ticket.get("category"),
                    "priority": ticket["priority"],
                    "urgency": ticket["urgency"],
                }
            )
            if st.button("Load messages", key=f"load_{ticket['id']}"):
                try:
                    detail = request("GET", f"/tickets/{ticket['id']}", token=token)
                    for message in detail.get("messages") or []:
                        st.markdown(f"**{message['role']}:** {message['content']}")
                except ApiError as exc:
                    st.error(str(exc))
