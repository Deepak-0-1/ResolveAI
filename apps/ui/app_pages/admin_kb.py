import streamlit as st
from api_client import ApiError, request

st.title("Knowledge base")
st.caption("Admin only — upload PDF, DOCX, TXT, or FAQ files.")

token = st.session_state.get("token")
user = st.session_state.get("user") or {}
if not token or user.get("role") != "admin":
    st.error("Admin access required.")
    st.stop()

uploaded = st.file_uploader(
    "Upload document",
    type=["pdf", "docx", "txt", "json", "faq"],
)
if uploaded is not None and st.button("Ingest", type="primary"):
    try:
        data = uploaded.getvalue()
        result = request(
            "POST",
            "/kb/documents",
            token=token,
            files={"file": (uploaded.name, data, uploaded.type or "application/octet-stream")},
            timeout=300.0,
        )
        st.success(
            f"Indexed `{result['filename']}` · {result['chunk_count']} chunks · {result['status']}"
        )
    except ApiError as exc:
        st.error(str(exc))

st.divider()
st.subheader("Indexed documents")
try:
    docs = request("GET", "/kb/documents", token=token)
except ApiError as exc:
    st.error(str(exc))
    st.stop()

if not docs:
    st.info("No documents yet. Run `resolveai-seed-kb` or upload above.")
else:
    st.dataframe(docs, width="stretch")

st.subheader("Test retrieval")
query = st.text_input("Search query", value="How do I reset my password?")
if st.button("Search"):
    try:
        hits = request(
            "POST",
            "/kb/search",
            token=token,
            json={"query": query, "limit": 5},
        )
        for hit in hits.get("hits") or []:
            st.markdown(
                f"**{hit.get('title') or hit.get('filename')}** "
                f"(score={hit['score']:.3f})\n\n{hit['text'][:400]}"
            )
            st.divider()
    except ApiError as exc:
        st.error(str(exc))
