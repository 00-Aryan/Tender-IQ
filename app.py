import time
import requests
import streamlit as st

API_BASE = "http://127.0.0.1:8000/api/v1"

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
                    st.error(f"Upload failed: {response.text}")
            except Exception as e:
                st.error(f"Could not connect to backend: {e}")

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
                        st.session_state.processing_error = f"Backend error: {status}"
                        st.session_state.app_state = "UPLOAD"
                        st.rerun()
                    
                    else:
                        time.sleep(2)
                else:
                    st.session_state.processing_error = f"Backend returned error {res.status_code}"
                    st.session_state.app_state = "UPLOAD"
                    st.rerun()
                    
            except Exception as e:
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
                        
                        st.write(answer)
                        
                        if citations:
                            with st.expander("Sources / Citations"):
                                for cite in citations:
                                    header = f"Page {cite.get('page_number', 'N/A')}"
                                    if cite.get('section'):
                                        header += f" | Section: {cite.get('section')}"
                                    st.markdown(f"**{header}**")
                                    st.caption(cite.get('snippet', ''))
                        
                        st.session_state.messages.append({
                            "role": "assistant",
                            "content": answer,
                            "citations": citations
                        })
                    else:
                        detail = res.json().get('detail', res.text)
                        st.error(f"Error from server: {detail}")
                except Exception as e:
                    st.error(f"Could not process your question: {str(e)}")