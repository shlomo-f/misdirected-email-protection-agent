import os
from typing import TypedDict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from src.agents.schemas import SecurityVerdict
from src.database.persona_store import PersonaStore
from src.database.vector_store import EmailVectorStore

load_dotenv()

persona_db = PersonaStore()
vector_db = EmailVectorStore()

class ProtectionState(TypedDict):
    draft_recipient: str
    draft_subject: str
    draft_body: str
    draft_attachments: list[str]
    target_persona: Optional[dict]
    historical_emails: list 
    all_possible_recipients: list[dict]
    verdict: Optional[SecurityVerdict]

def retrieve_context_node(state: ProtectionState) -> ProtectionState:
    """Fetches target context and searches for potential correct recipients."""
    recipient = state["draft_recipient"]
    subject = state["draft_subject"]
    body = state["draft_body"]
    
    print(f"🔍 [Agent]: Gathering hybrid memory for {recipient}...")
    
    # Fetch Entity Memory (Persona) for the current recipient
    persona = persona_db.get_persona(recipient)

    if persona:
        print("   -> Persona found. Proceeding to evaluation.")
    else:
        print("   -> Unknown recipient. (Treating as low risk/new connection).")
    
    # Fetch Episodic Memory (Raw Vectors) for current recipient
    search_query = f"{subject} {body}"
    history = vector_db.query_history(
        contact_email=recipient, 
        query_text=search_query, 
        k=5
    )
    
    # Find "Similar Name" alternative candidates (The "Wrong Joe" check)
    email_prefix = recipient.split("@")[0].lower()
    
    name_matches = persona_db.search_by_name_or_prefix(email_prefix) if hasattr(persona_db, 'search_by_name_or_prefix') else []
    
    # Global Semantic Search (The "Project Match" check)
    global_matches = vector_db.query_history_global(query_text=search_query, k=3) if hasattr(vector_db, 'query_history_global') else []
    
    global_candidates = []
    for doc in global_matches:
        past_recipient = doc.metadata.get("recipient_email")
        if past_recipient and past_recipient != recipient:
            p_match = persona_db.get_persona(past_recipient)
            if p_match:
                global_candidates.append(p_match)

    # Deduplicate alternative candidates and filter out current recipient
    candidates_dict = {}
    for p in (name_matches + global_candidates):
        p_dict = p.model_dump() if hasattr(p, "model_dump") else p
        if p_dict.get("email") != recipient:
            candidates_dict[p_dict["email"]] = p_dict
    
    print(f"   -> Found Persona: {'Yes' if persona else 'No'}")
    print(f"   -> Found Raw Emails: {len(history)}")
    print(f"   -> Found {len(candidates_dict)} alternative contacts for cross-referencing.")
        
    return {
        "target_persona": persona,
        "historical_emails": history,
        "all_possible_recipients": list(candidates_dict.values())
    }

def evaluation_node(state: ProtectionState) -> ProtectionState:
    """The Brain: Compares the draft to Persona + Raw History and cross-references candidates."""
    print("🧠 [Agent]: Evaluating draft against hybrid memory and alternative recipients...")
    
    # Format the top 5 historical emails into a readable string
    history_text = "No relevant prior emails found."
    if state["historical_emails"]:
        history_text = ""
        for i, doc in enumerate(state["historical_emails"]):
            subj = doc.metadata.get("subject", "Unknown")
            date = doc.metadata.get("date", "Unknown")
            atts = doc.metadata.get("attachments", "None")
            body_snippet = doc.page_content[:300] 
            
            history_text += f"\n--- PAST EMAIL {i+1} ---\n"
            history_text += f"Date: {date}\nSubject: {subj}\nAttachments: {atts}\n"
            history_text += f"Body Snippet: {body_snippet}...\n"

    # Format Alternative Candidates string using the updated structured Persona fields
    candidates_text = "No alternative contacts found."
    if state["all_possible_recipients"]:
        candidates_text = ""
        for p in state["all_possible_recipients"]:
            candidates_text += f"\n--- ALTERNATIVE CONTACT ---\n"
            candidates_text += f"Email: {p.get('email')}\n"
            candidates_text += f"Names: {', '.join(p.get('inferred_names', []))}\n"
            candidates_text += f"Companies: {', '.join(p.get('company', p.get('company', [])))}\n"
            candidates_text += f"Known Topics: {', '.join(p.get('known_topics', []))}\n"

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(SecurityVerdict)
    
    prompt = f"""
    You are an AI Security Advisor embedded in an email client. Your job is to prevent misdirected emails.
    
    Evaluate the following outgoing draft against the recipient's historical baseline.
    
    === OUTGOING DRAFT ===
    To: {state['draft_recipient']}
    Subject: {state['draft_subject']}
    Body: {state['draft_body']}
    Attachments: {', '.join(state['draft_attachments']) if state['draft_attachments'] else 'None'}
    
    === BASELINE: RECIPIENT PERSONA (Summary) ===
    {state['target_persona'] if state['target_persona'] else "No verified persona exists."}
    
    === BASELINE: RELEVANT PAST EMAILS (Top 5 matches) ===
    {history_text}
    
    === ALTERNATIVE CANDIDATES LIST ===
    Review this list of alternative contacts. If the current draft matches one of these personas 
    significantly better than the current recipient, you will suggest them.
    {candidates_text}
    
    INSTRUCTIONS:
    1. Check for Contradictions: Does the draft reference topics, attachments, or companies that severely clash with BOTH the Persona summary and the Past Emails?
    2. Missing Context is Suspicious: If the draft is highly technical or sensitive (e.g., budget sheets) but the Past Emails are strictly casual or about a different project, flag it.
    3. Calculate a risk_score (0-100). If the risk is high enough to warrant a user alert, set status to WARN. Otherwise, SAFE.
    4. Suggestion Logic: If status is WARN, check the ALTERNATIVE CANDIDATES LIST. If an alternative contact matches the topic, name prefix (e.g., "Wrong Joe" issue), or company mentioned in the draft significantly better than the current recipient, populate `suggested_recipient` and `suggestion_reason`. Otherwise, leave them as None.

    OUTPUT FORMAT:
    Write a highly concise 'reasoning' block. Do NOT write paragraphs. 
    Use exactly 2-3 short, punchy bullet points detailing the specific anomalies or risks found. 
    Each bullet should be under 15 words.
    Order them by importance based on your opinion.
    """
    
    verdict = structured_llm.invoke(prompt)
    return {"verdict": verdict}

# Build the Graph
workflow = StateGraph(ProtectionState)

workflow.add_node("retrieve", retrieve_context_node)
workflow.add_node("evaluate", evaluation_node)

workflow.add_edge(START, "retrieve")
workflow.add_edge("retrieve", "evaluate")
workflow.add_edge("evaluate", END)

protection_app = workflow.compile()

# --- Test Script: Simulating the UI ---
if __name__ == "__main__":
    # Define the correct recipient data structure
    correct_robert_persona = {
        "email": "robert@global-energy.com",
        "inferred_names": ["Robert"],
        "company": ["Global Energy", "NY Clean-Gen Plant"],
        "job_title": "Plant Owner / Operations Director",
        "relationship_to_sender": "Client",
        "known_topics": ["NY Clean-Gen Plant", "NERC-CIP Compliance", "SCADA Ingestion", "Modbus/TCP blocks"],
        "last_updated": "2026-05-24",
        "last_talked": "2026-05-24"
    }

    # 2. Mock the DB instances to return our test data dynamically
    # This prevents the retrieve node from wiping out your test state
    persona_db.get_persona = lambda email: None  # The wrong email has no persona yet
    persona_db.search_by_name_or_prefix = lambda prefix: [correct_robert_persona] if prefix == "robert" else []
    vector_db.query_history = lambda contact_email, query_text, k: []
    vector_db.query_history_global = lambda query_text, k: []

    # 3. Define the live draft (can start empty for target/historical fields)
    live_draft = {
        "draft_recipient": "robert@global-vector-dynamics.com",
        "draft_subject": "NY Clean-Gen - Quick IAM Question",
        "draft_body": "Hi Robert,\n\nFollowing up on the NERC-CIP requirements, could you loop in your Identity Security lead? We need to quickly align on the IAM and access control setup for the plant operators before Thursday's call.\n\nBest,\nJoe",
        "draft_attachments": [],
        "all_possible_recipients": [], 
        "target_persona": None, 
        "historical_emails": [] 
    }
    
    print("\n" + "="*50)
    print("USER CLICKS 'SEND' (Simulating Autofill Error)")
    print("="*50 + "\n")
    
    # Run the full workflow app
    final_state = protection_app.invoke(live_draft)
    verdict = final_state["verdict"]
    
    # --- UI Presentation Logic ---
    if verdict.status == "SAFE":
        print("✅ Email sent successfully.")
    elif verdict.status == "WARN":
        print("\n⚠️  [UI POPUP TRIGGERED]  ⚠️")
        print(f"Risk Score: {verdict.risk_score}/100")
        print(f"Agent Reasoning: \n{verdict.reasoning}")
        
        if verdict.suggested_recipient:
            print(f"\n💡 Did you mean to send this to: {verdict.suggested_recipient}?")
            print(f"   Reason: {verdict.suggestion_reason}")
            print("-" * 30)