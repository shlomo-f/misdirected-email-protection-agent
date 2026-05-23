import streamlit as st
import time
import os
import tempfile
from src.database.vector_store import EmailVectorStore
from src.agents.protection_graph import protection_app
from src.agents.ingestion_graph import ingestion_app

# --- UI CONFIGURATION ---
st.set_page_config(page_title="Misdirected Email Protection", layout="wide", page_icon="🛡️")

# --- DATABASE INITIALIZATION ---
@st.cache_resource
def get_vector_store():
    return EmailVectorStore()

store = get_vector_store()

# --- SESSION STATE INITIALIZATION ---
if "memory_initialized" not in st.session_state:
    st.session_state.memory_initialized = False
if "verdict" not in st.session_state:
    st.session_state.verdict = None
if "current_draft" not in st.session_state:
    st.session_state.current_draft = None
if "ingestion_method" not in st.session_state:
    st.session_state.ingestion_method = None  # Tracks "upload" or "local"

# --- GLOBAL DATABASE MONITOR (Visible in both Phase 1 and Phase 2) ---
st.set_page_config(initial_sidebar_state="collapsed")

with st.sidebar:
    st.header("📊 Database Monitor")
    try:
        db_content = store.vector_db.get()
        record_count = len(db_content.get('ids', []))
        
        st.metric(label="Active Emails in ChromaDB", value=record_count)
        
        if record_count > 0:
            with st.expander("Show stored Email IDs"):
                st.json(db_content['ids'])
        else:
            st.info("ChromaDB collection is empty.")
    except Exception as e:
        st.error(f"Error reading DB status: {e}")


# --- HEADER ---
st.title("🛡️ LLM Based Misdirected Email Protection System")
st.markdown("A stateful agent that intercepts misdirected emails and learns from overrides.")
st.divider()

# ==========================================
# PHASE 1: AGENT MEMORY INGESTION
# ==========================================
if not st.session_state.memory_initialized:
    st.header("Phase 1: Train the Agent's Memory")
    st.write("Before the Gatekeeper can protect your outbound emails, it needs to simulate learning your inbox. Upload past emails, or use the pre-loaded test data to build the initial vector database and persona summaries.")
    
    col_upload, col_default = st.columns(2)
    
    with col_upload:
        with st.container(border=True):
            st.subheader("Option A: Upload .eml Files")
            uploaded_files = st.file_uploader("Upload historical emails", type=['eml'], accept_multiple_files=True)
            
            if st.button("Process Uploads", type="primary", disabled=not uploaded_files):
                with st.status("Ingesting Emails...", expanded=True) as status:
                    for uploaded_file in uploaded_files:
                        st.write(f"🔄 Processing: {uploaded_file.name}")
                        
                        # Save the uploaded RAM file to a temporary disk file so the parser can read it
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".eml") as tmp_file:
                            tmp_file.write(uploaded_file.getvalue())
                            tmp_file_path = tmp_file.name
                        
                        # Trigger the background learning agent
                        ingestion_app.invoke({"email_file_path": tmp_file_path})
                        
                        # Clean up the temp file
                        os.remove(tmp_file_path)
                        
                    status.update(label="Memory Initialized Successfully!", state="complete", expanded=False)
                    time.sleep(1)
                    st.session_state.ingestion_method = "upload"
                    st.session_state.memory_initialized = True
                    st.rerun()

    with col_default:
        with st.container(border=True):
            st.subheader("Option B: Ingest All Pre-loaded Data")
            st.write("Automatically scan the `data/raw_emails/` directory and ingest every `.eml` file found to build your initial knowledge base.")
            
            if st.button("Load All Local Emails", type="secondary", use_container_width=True):
                email_dir = os.path.join("data", "raw_emails")
                
                if not os.path.exists(email_dir):
                    st.error(f"❌ The directory `{email_dir}` does not exist!")
                else:
                    # Gather all files ending in .eml
                    eml_files = [f for f in os.listdir(email_dir) if f.lower().endswith('.eml')]
                    
                    if not eml_files:
                        st.warning(f"⚠️ No `.eml` files found in `{email_dir}`.")
                    else:
                        with st.status(f"Ingesting {len(eml_files)} emails...", expanded=True) as status:
                            for filename in eml_files:
                                file_path = os.path.join(email_dir, filename)
                                
                                st.write(f"🔄 Processing: {filename}")
                                ingestion_app.invoke({"email_file_path": file_path})
                                
                            status.update(label="All local data ingested!", state="complete", expanded=False)
                            time.sleep(1)
                            st.session_state.ingestion_method = "local"
                            st.session_state.memory_initialized = True
                            st.rerun()

# ==========================================
# PHASE 2: THE EMAIL CLIENT & GATEKEEPER
# ==========================================
else:
    if st.button("← Reset Agent Memory & Start Over"):
        # Wipe and clear TinyDB
        tinydb_path = os.path.join("data", "personas", "personas.json")
        #email_vector_strore_path = os.path.join("data", "email_vectore_store", "personas.json")
        
        try:
            os.makedirs(os.path.dirname(tinydb_path), exist_ok=True)

            with open(tinydb_path, 'w', encoding='utf-8') as f:
                f.write('{}') 
                
            # This will now reference the globally active store object and clear ChromaDB
            store.clear_store()
            
            st.toast("🧹 Database successfully cleared!", icon="🗑️")
            time.sleep(1.5)
            print("\n🧹 Database file successfully wiped and cleared!\n")

        except Exception as e:
            st.error(f"Failed to clear database content: {e}")
            print(f"\n[System Reset Error] ❌ Failed to clear database content: {e}\n")
            
        # Clear the UI state in RAM
        st.session_state.memory_initialized = False
        st.session_state.verdict = None
        st.session_state.current_draft = None
        st.session_state.ingestion_method = None
        st.rerun()
        
    st.divider()
 
    col1, col2 = st.columns([1, 1.2])

    # LEFT COLUMN: THE EMAIL CLIENT
    with col1:
        st.header("✉️ Compose Email")
        
        # Determine default values based on the ingestion method used
        if st.session_state.ingestion_method == "local":
            default_recipient = "robert@global-vector-dynamics.com"
            default_subject = "TechStars Q4 Marketing Reallocation"
            default_body = "Hi Robert,\n\nPlease review the attached TechStars marketing spend. We need to cut the ad budget by 15%."
            default_attachments = "TechStars_Budget_v2.pdf"
        else:
            default_recipient = ""
            default_subject = ""
            default_body = ""
            default_attachments = ""

        with st.container(border=True):
            recipient = st.text_input("To:", value=default_recipient)
            subject = st.text_input("Subject:", value=default_subject)
            body = st.text_area("Body:", height=200, value=default_body)
            attachments_input = st.text_input(
                "Attachments:", 
                value=default_attachments,
                help="Currently only takes names of files, not the actual files, comma separated."
            )
            
            if st.button("🔍 Evaluate Draft (Simulate Send)", type="primary", use_container_width=True):
                attachments_list = [f.strip() for f in attachments_input.split(",") if f.strip()]
                
                st.session_state.current_draft = {
                    "draft_recipient": recipient,
                    "draft_subject": subject,
                    "draft_body": body,
                    "draft_attachments": attachments_list
                }
                st.session_state.verdict = None

    # RIGHT COLUMN: THE AGENT'S BRAIN
    with col2:
        st.header("🧠 Agent Terminal")
        
        if not st.session_state.current_draft:
            st.info("Waiting for draft submission...")
            
        elif st.session_state.current_draft and st.session_state.verdict is None:
            with st.status("Agent is analyzing hybrid memory...", expanded=True) as status:
                st.write("🔍 Querying TinyDB for Entity Persona...")
                time.sleep(0.5) 
                st.write("🔍 Querying ChromaDB for Vector History...")
                time.sleep(0.5)
                st.write("🧠 LLM is evaluating semantic clash...")
                
                final_state = protection_app.invoke(st.session_state.current_draft)
                st.session_state.verdict = final_state["verdict"]
                
                status.update(label="Analysis Complete!", state="complete", expanded=False)
                st.rerun() 

        if st.session_state.verdict:
            verdict = st.session_state.verdict
            
            if verdict.status == "SAFE":
                st.success("✅ **STATUS: SAFE**")
                st.write(verdict.reasoning)
                
                if st.button("🚀 Send Email", use_container_width=True):
                    st.toast("Email sent successfully!")
                    ingestion_app.invoke({"live_email_dict": st.session_state.current_draft})
                    st.session_state.verdict = None
                    st.session_state.current_draft = None
                    st.rerun()
                    
            elif verdict.status == "WARN":
                st.error(f"⚠️ **STATUS: WARNING (Risk Score: {verdict.risk_score}/100)**")
                st.write(f"**Agent Reasoning:** \n{verdict.reasoning}")
                
                if verdict.flagged_context:
                    st.warning(f"**Flagged Entities:** {', '.join(verdict.flagged_context)}")
                
                st.divider()
                st.markdown("### Action Required")
                
                col_a, col_b = st.columns(2)
                      
                with col_a:
                    if st.button("✏️ Back to Editing", use_container_width=True):
                        st.session_state.verdict = None
                        
                        st.session_state.current_draft = None
                        
                        st.rerun()

                with col_b:
                    if st.button("🚨 Override & Send Anyway", type="primary", use_container_width=True):
                        with st.spinner("Sending email and updating memory agent..."):
                            ingestion_app.invoke({"live_email_dict": st.session_state.current_draft})
                            
                        st.success("Email sent! The Agent has updated the Persona to learn from this override.")
                        time.sleep(2)
                        st.session_state.verdict = None
                        st.session_state.current_draft = None
                        st.rerun()