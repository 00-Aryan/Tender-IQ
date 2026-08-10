import os
import re
import tempfile
import streamlit as st

from tender_iq.document_processor.loader import load_tender_pdf
from tender_iq.document_processor.chunker import chunk_tender_documents
from tender_iq.vector_store.chroma_store import store_tender
from tender_iq.rag.tender_rag import build_rag_chain

st.set_page_config(page_title="TenderIQ", layout="centered")

# ── INITIALIZE ALL SESSION STATE KEYS ─────────────────────────────────────────
st.session_state.setdefault("app_state", "UPLOAD")
st.session_state.setdefault("tender_id", None)
st.session_state.setdefault("rag_chain", None)
st.session_state.setdefault("chunks", None)
st.session_state.setdefault("messages", [])
st.session_state.setdefault("processing_error", None)
st.session_state.setdefault("tmp_path", None)

# ── UPLOAD ──────────────────────────────────────────────────────────────────
if st.session_state.app_state == "UPLOAD":
    st.title("TenderIQ")
    st.write("Upload a vehicle tender PDF to start asking questions about it.")

    if st.session_state.processing_error:
        st.error(st.session_state.processing_error)
        st.session_state.processing_error = None

    uploaded_file = st.file_uploader("Upload tender PDF", type=["pdf"])

    if uploaded_file is not None:
        tender_id = re.sub(r"[^a-zA-Z0-9_-]", "_", uploaded_file.name.replace(".pdf", ""))

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        st.session_state.tender_id = tender_id
        st.session_state.tmp_path = tmp_path
        st.session_state.app_state = "PROCESSING"
        st.rerun()

# ── PROCESSING ───────────────────────────────────────────────────────────────
elif st.session_state.app_state == "PROCESSING":
    st.title("TenderIQ")
    st.write(f"Processing: {st.session_state.tender_id}")

    with st.spinner("This may take up to 2 minutes..."):
        try:
            tmp_path = st.session_state.tmp_path
            tender_id = st.session_state.tender_id

            markdown_text = load_tender_pdf(tmp_path)
            chunks = chunk_tender_documents(markdown_text)

            store_tender(chunks, tender_id)

            # Preserve chunks and built chain across session reruns
            st.session_state.chunks = chunks
            st.session_state.rag_chain = build_rag_chain(tender_id, chunks)

            if os.path.exists(tmp_path):
                os.unlink(tmp_path)

            st.session_state.app_state = "CHAT"
            st.rerun()

        except FileNotFoundError as e:
            st.session_state.processing_error = f"Could not read the file: {str(e)}"
            st.session_state.app_state = "UPLOAD"
            st.rerun()
        except Exception as e:
            st.session_state.processing_error = f"Processing failed: {str(e)}"
            st.session_state.app_state = "UPLOAD"
            st.rerun()

# ── CHAT ─────────────────────────────────────────────────────────────────────
elif st.session_state.app_state == "CHAT":
    st.title("TenderIQ")
    st.caption(f"Tender: {st.session_state.tender_id}")

    if st.button("Upload a different tender"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    st.divider()

    # Render previous discussion thread
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    prompt = st.chat_input("Ask a question about this tender...")

    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    response = st.session_state.rag_chain.invoke(prompt)
                    st.write(response)
                    st.session_state.messages.append({"role": "assistant", "content": response})
                except Exception as e:
                    st.error(f"Could not process your question: {str(e)}")