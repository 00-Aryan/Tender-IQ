import logging
import time
import requests
import streamlit as st

logger = logging.getLogger(__name__)

API_BASE = "http://127.0.0.1:8000/api/v1"
LATENCY_STAGE_LABELS = {
    "chunk_loading_ms": "Chunk Loading",
    "bm25_build_ms": "BM25 Build",
    "query_expansion_ms": "Query Expansion",
    "retrieval_ms": "Retrieval",
    "answer_generation_ms": "Answer Generation",
}


def render_latency_breakdown(latency_breakdown):
    if not isinstance(latency_breakdown, dict) or not latency_breakdown:
        return

    with st.expander("⚡ Detailed Latency Breakdown"):
        for key, label in LATENCY_STAGE_LABELS.items():
            duration = latency_breakdown.get(key)
            value = f"{duration:.2f} ms" if isinstance(duration, (int, float)) else "N/A"
            st.markdown(f"- **{label}:** {value}")

st.set_page_config(page_title="TenderIQ", layout="centered")

# ── INITIALIZE ALL SESSION STATE KEYS ─────────────────────────────────────────
st.session_state.setdefault("app_state", "UPLOAD")
st.session_state.setdefault("job_id", None)
st.session_state.setdefault("tender_id", None)
st.session_state.setdefault("messages", [])
st.session_state.setdefault("processing_error", None)

# ── UPLOAD ──────────────────────────────────────────────────────────────────
if st.session_state.app_state == "UPLOAD":
    st.title("TenderIQ")
    st.write("Upload a vehicle tender PDF to start asking questions about it.")

    if st.session_state.processing_error:
        st.error(st.session_state.processing_error)
        st.session_state.processing_error = None

    uploaded_file = st.file_uploader("Upload tender PDF", type=["pdf"])

    if uploaded_file is not None:
        with st.spinner("Uploading to server..."):
            files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/pdf")}
            try:
                response = requests.post(f"{API_BASE}/tenders/upload", files=files)
                if response.status_code in [201, 202]:
                    data = response.json()
                    st.session_state.job_id = data["tender_id"]
                    st.session_state.app_state = "PROCESSING"
                    st.rerun()
                else:
                    logger.warning("Tender upload failed with HTTP status %s", response.status_code)
                    st.error("Upload failed. Please verify your file and try again.")
            except Exception:
                logger.exception("Could not connect to the backend during tender upload")
                st.error("Could not connect to the service. Please try again.")

# ── PROCESSING (The Polling Loop) ───────────────────────────────────────────
elif st.session_state.app_state == "PROCESSING":
    st.title("TenderIQ")

    with st.spinner("Working on it. This may take a moment..."):
        job_id = st.session_state.job_id
        is_done = False
        
        while not is_done:
            try:
                res = requests.get(f"{API_BASE}/tenders/{job_id}/specs")
                
                if res.status_code == 200:
                    data = res.json()
                    status = data.get("status", "")
                    
                    if status == "completed":
                        specs = data.get("specs", {})
                        # Grab the real Bid ID or fallback to job_id
                        st.session_state.tender_id = specs.get("bid_id", job_id)
                        is_done = True
                    
                    elif status.startswith("failed"):
                        st.session_state.processing_error = "Tender processing failed. Please try another PDF."
                        st.session_state.app_state = "UPLOAD"
                        st.rerun()
                    
                    else:
                        time.sleep(2)
                else:
                    logger.warning("Tender status request failed with HTTP status %s", res.status_code)
                    st.session_state.processing_error = "Could not check tender processing status. Please try again."
                    st.session_state.app_state = "UPLOAD"
                    st.rerun()
                    
            except Exception:
                logger.exception("Could not check tender processing status")
                st.session_state.processing_error = "Lost connection to backend during polling."
                st.session_state.app_state = "UPLOAD"
                st.rerun()
        
        st.session_state.app_state = "CHAT"
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

    # Render previous discussion thread and citations
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])
            
            if message.get("latency_ms") is not None:
                token_str = f" | 🪙 {message['tokens_used']} tokens" if message.get("tokens_used") else ""
                st.caption(f"⚡ {message['latency_ms']} ms{token_str}")
            render_latency_breakdown(message.get("latency_breakdown_ms"))

            if "citations" in message and message["citations"]:
                with st.expander("Sources / Citations"):
                    for cite in message["citations"]:
                        header = f"Page {cite.get('page_number', 'N/A')}"
                        if cite.get('section'):
                            header += f" | Section: {cite.get('section')}"
                        st.markdown(f"**{header}**")
                        st.caption(cite.get('snippet', ''))

    prompt = st.chat_input("Ask a question about this tender...")

    if prompt:
        with st.chat_message("user"):
            st.write(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    payload = {
                        "tender_id": st.session_state.tender_id,
                        "query": prompt
                    }
                    res = requests.post(f"{API_BASE}/chat/", json=payload)
                    
                    if res.status_code == 200:
                        res_data = res.json()
                        answer = res_data.get("answer", "")
                        citations = res_data.get("citations", [])
                        latency_ms = res_data.get("latency_ms")
                        latency_breakdown_ms = res_data.get("latency_breakdown_ms", {})
                        tokens_used = res_data.get("tokens_used")
                        
                        st.write(answer)

                        if latency_ms is not None:
                            token_str = f" | 🪙 {tokens_used} tokens" if tokens_used else ""
                            st.caption(f"⚡ {latency_ms} ms{token_str}")
                        render_latency_breakdown(latency_breakdown_ms)
                        
                        # if citations:
                        #     with st.expander("Sources / Citations"):
                        #         for cite in citations:
                        #             header = f"Page {cite.get('page_number', 'N/A')}"
                        #             if cite.get('section'):
                        #                 header += f" | Section: {cite.get('section')}"
                        #             st.markdown(f"**{header}**")
                        #             st.caption(cite.get('snippet', ''))
                        
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer,
                            "citations": citations,
                            "latency_ms": latency_ms,
                            "latency_breakdown_ms": latency_breakdown_ms,
                            "tokens_used": tokens_used
                        })
                    else:
                        logger.warning("Chat request failed with HTTP status %s", res.status_code)
                        st.error("Could not process your question. Please try again.")
                except Exception:
                    logger.exception("Could not process chat request")
                    st.error("Could not process your question. Please try again.")