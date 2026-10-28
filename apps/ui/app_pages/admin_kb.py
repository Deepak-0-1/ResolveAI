"""Knowledge Base Management — Document upload, ingestion telemetry, and vector retrieval testing."""

from __future__ import annotations

import streamlit as st
from api_client import (
    ApiError,
    list_kb_documents,
    search_kb,
    upload_kb_document,
)
from theme import (
    apply_theme,
    format_datetime,
    get_status_badge_html,
    render_empty_state,
    render_header,
    render_stat_card,
)

apply_theme()

token = st.session_state.get("token")
user = st.session_state.get("user") or {}

if not token or user.get("role") != "admin":
    st.error("Administrator access required to manage the knowledge base.")
    st.stop()

render_header(
    "Knowledge Base Management",
    "Upload enterprise documentation, verify vector ingestion chunks, and test hybrid retrieval ranking.",
    badge="ADMIN CONSOLE",
)

# Fetch current documents
try:
    with st.spinner("Loading document repository…"):
        docs = list_kb_documents(token)
except ApiError as exc:
    st.error(f"Failed to fetch documents: {exc}")
    docs = []

indexed_docs = [d for d in docs if d["status"] == "indexed"]
failed_docs = [d for d in docs if d["status"] == "failed"]
total_chunks = sum(d.get("chunk_count", 0) for d in indexed_docs)

# Top Stats Row
s_col1, s_col2, s_col3, s_col4 = st.columns(4)
with s_col1:
    render_stat_card("Total Documents", len(docs), "All submitted files")
with s_col2:
    render_stat_card("Indexed & Active", len(indexed_docs), "Vectors stored in Qdrant")
with s_col3:
    render_stat_card("Failed Ingestions", len(failed_docs), "Parsing or embedding error")
with s_col4:
    render_stat_card("Active Chunks", total_chunks, "Hybrid searchable units")

st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# ==============================================================================
# SECTION 1: DOCUMENT UPLOAD & INGESTION
# ==============================================================================
st.markdown("### Document Ingestion")
st.caption("Upload documents to be parsed, chunked, and embedded into Qdrant vector storage.")

if "ingestion_in_progress" not in st.session_state:
    st.session_state.ingestion_in_progress = False

with st.container(border=True):
    u_col1, u_col2 = st.columns([3, 1])
    with u_col1:
        uploaded_file = st.file_uploader(
            "Choose a document file",
            type=["pdf", "docx", "txt", "json", "faq"],
            help="Supported formats: PDF, DOCX, TXT, JSON, FAQ. Maximum size: 10 MB.",
        )
    with u_col2:
        st.markdown(
            """
            <div style="font-size:0.75rem; color:#5E6C84; padding-top:1.5rem;">
                <strong>Formats Supported:</strong><br>
                • <code>.pdf</code> (PyPDF parsing)<br>
                • <code>.docx</code> (Word document)<br>
                • <code>.txt</code> / <code>.faq</code> / <code>.json</code>
            </div>
            """,
            unsafe_allow_html=True,
        )

    ingest_disabled = uploaded_file is None or st.session_state.ingestion_in_progress
    if st.button(
        "🚀 Ingest Document into Vector Store",
        type="primary",
        disabled=ingest_disabled,
    ):
        st.session_state.ingestion_in_progress = True
        with st.spinner(f"Ingesting '{uploaded_file.name}': parsing, chunking, and embedding vectors…"):
            try:
                data = uploaded_file.getvalue()
                res = upload_kb_document(
                    filename=uploaded_file.name,
                    data=data,
                    content_type=uploaded_file.type or "application/octet-stream",
                    token=token,
                )
                st.session_state.ingestion_in_progress = False
                st.success(
                    f"✅ Successfully indexed `{res['filename']}`: generated **{res['chunk_count']}** chunks in vector storage."
                )
                st.rerun()
            except ApiError as exc:
                st.session_state.ingestion_in_progress = False
                st.error(f"Ingestion failed: {exc}")
            except Exception as exc:
                st.session_state.ingestion_in_progress = False
                st.error(f"Network error during upload: {exc}")

st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# ==============================================================================
# SECTION 2: REPOSITORY INVENTORY (INDEXED VS FAILED)
# ==============================================================================
tab_indexed, tab_failed = st.tabs([
    f"Indexed Documents ({len(indexed_docs)})",
    f"Failed Ingestions ({len(failed_docs)})",
])

with tab_indexed:
    if not indexed_docs:
        render_empty_state("No Indexed Documents", "Upload a document above or seed with documentation files.")
    else:
        st.dataframe(
            [
                {
                    "Document Title": d["title"],
                    "Filename": d["filename"],
                    "Format": d["source_type"].upper(),
                    "Status": "INDEXED",
                    "Chunks": d["chunk_count"],
                    "Indexed At": format_datetime(d.get("created_at")),
                }
                for d in indexed_docs
            ],
            width="stretch",
        )

with tab_failed:
    if not failed_docs:
        render_empty_state("No Ingestion Failures", "All uploaded documents have been ingested cleanly without errors.")
    else:
        for fd in failed_docs:
            with st.container(border=True):
                st.markdown(f"**{fd['filename']}** ({fd['source_type'].upper()})")
                st.caption(f"Attempted at {format_datetime(fd.get('created_at'))}")
                st.error(f"Error: {fd.get('error_message') or 'Unknown parsing error'}")

st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

# ==============================================================================
# SECTION 3: RETRIEVAL & CHUNK INSPECTOR
# ==============================================================================
st.markdown("### Vector & Hybrid Retrieval Inspector")
st.caption("Perform test queries against active vector embeddings to inspect retrieved chunk ranks, scores, and text excerpts.")

with st.container(border=True):
    r_col1, r_col2 = st.columns([3, 1])
    with r_col1:
        test_query = st.text_input(
            "Test Search Query",
            value="How do I reset my password?",
            placeholder="Type a sample user inquiry…",
        )
    with r_col2:
        top_k = st.slider("Top-K Hits", min_value=1, max_value=10, value=4)

    run_search = st.button("🔍 Execute Test Retrieval", type="primary")

if run_search and test_query.strip():
    with st.spinner("Searching hybrid vector index…"):
        try:
            search_res = search_kb(query=test_query.strip(), token=token, limit=top_k)
            hits = search_res.get("hits") or []

            if not hits:
                st.info("No matching chunks found above minimum similarity threshold.")
            else:
                st.markdown(f"#### Retrieval Results ({len(hits)} matching chunks)")
                for idx, hit in enumerate(hits):
                    score = hit.get("score", 0.0)
                    title = hit.get("title") or hit.get("filename") or f"Doc #{hit.get('document_id', '')[:8]}"
                    chunk_idx = hit.get("chunk_index", 0)

                    with st.container(border=True):
                        h_col1, h_col2 = st.columns([3, 1])
                        with h_col1:
                            st.markdown(f"**Rank #{idx + 1}** · {title} · <span style='font-size:0.75rem; color:#64748B;'>Chunk Index: {chunk_idx}</span>", unsafe_allow_html=True)
                        with h_col2:
                            st.markdown(f"<div style='text-align:right;'><span class='badge badge-open'>Score: {score:.4f}</span></div>", unsafe_allow_html=True)

                        st.markdown(
                            f"""
                            <div style="background:#F8FAFC; border:1px solid #E2E8F0; border-radius:6px; padding:0.75rem 1rem; font-size:0.85rem; color:#334155; line-height:1.45; margin-top:0.4rem;">
                                {hit.get('text', '')}
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        with st.expander("Inspect Chunk Metadata", expanded=False):
                            st.json(
                                {
                                    "chunk_id": hit.get("chunk_id"),
                                    "document_id": hit.get("document_id"),
                                    "chunk_index": hit.get("chunk_index"),
                                    "source_type": hit.get("source_type"),
                                    "score": hit.get("score"),
                                }
                            )
        except ApiError as exc:
            st.error(f"Search failed: {exc}")
