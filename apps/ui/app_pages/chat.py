import streamlit as st
from api_client import ApiError, request

st.title("Support chat")
st.caption("Grounded answers with citations. Sensitive or weak matches escalate.")

token = st.session_state.get("token")
if not token:
    st.warning("Please sign in first.")
    st.stop()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for turn in st.session_state.chat_history:
    with st.chat_message("user"):
        st.markdown(turn["user"])
    with st.chat_message("assistant"):
        st.markdown(turn["assistant"])
        if turn.get("citations"):
            with st.expander("Citations"):
                for cite in turn["citations"]:
                    st.markdown(
                        f"**[{cite['index']}]** {cite.get('title') or cite.get('filename')} "
                        f"(score={cite['score']:.3f})\n\n{cite['snippet']}"
                    )
        meta = []
        if turn.get("status"):
            meta.append(f"status={turn['status']}")
        if turn.get("category"):
            meta.append(f"category={turn['category']}")
        if turn.get("trace"):
            meta.append(" → ".join(turn["trace"]))
        if meta:
            st.caption(" · ".join(meta))

prompt = st.chat_input("Ask about NovaDesk billing, accounts, API, privacy…")
if prompt:
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            try:
                result = request(
                    "POST",
                    "/chat",
                    token=token,
                    json={"message": prompt},
                    timeout=180.0,
                )
            except ApiError as exc:
                st.error(str(exc))
                st.stop()

        st.markdown(result["answer"])
        if result.get("citations"):
            with st.expander("Citations", expanded=True):
                for cite in result["citations"]:
                    st.markdown(
                        f"**[{cite['index']}]** {cite.get('title') or cite.get('filename')} "
                        f"(score={cite['score']:.3f})\n\n{cite['snippet']}"
                    )
        if result.get("status") == "escalated":
            st.warning(
                title="Escalated",
                body=result.get("escalation_reason") or "Handed off to a human agent.",
            )
        st.caption(
            f"{result.get('status')} · {result.get('category')}/{result.get('priority')} · "
            + " → ".join(result.get("trace") or [])
        )

        cols = st.container(horizontal=True)
        with cols:
            if st.button("Helpful", key=f"up_{len(st.session_state.chat_history)}"):
                try:
                    request(
                        "POST",
                        "/feedback",
                        token=token,
                        json={"rating": 1, "comment": "thumbs up from chat"},
                    )
                    st.toast("Thanks for the feedback")
                except ApiError as exc:
                    st.error(str(exc))
            if st.button("Not helpful", key=f"down_{len(st.session_state.chat_history)}"):
                try:
                    request(
                        "POST",
                        "/feedback",
                        token=token,
                        json={"rating": -1, "comment": "thumbs down from chat"},
                    )
                    st.toast("Thanks — we logged that")
                except ApiError as exc:
                    st.error(str(exc))

    st.session_state.chat_history.append(
        {
            "user": prompt,
            "assistant": result["answer"],
            "citations": result.get("citations") or [],
            "status": result.get("status"),
            "category": result.get("category"),
            "trace": result.get("trace") or [],
        }
    )
