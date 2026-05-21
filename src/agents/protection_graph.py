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
    verdict: Optional[SecurityVerdict]

def retrieve_context_node(state: ProtectionState) -> ProtectionState:
    """Fetches both the recipient's profile and raw historical context."""
    recipient = state["draft_recipient"]
    print(f"🔍 [Agent]: Gathering hybrid memory for {recipient}...")
    
    # Fetch Entity Memory (Persona)
    persona = persona_db.get_persona(recipient)

    if persona:
        print("   -> Persona found. Proceeding to evaluation.")
    else:
        print("   -> Unknown recipient. (Treating as low risk/new connection).")
    
    # Fetch Episodic Memory (Raw Vectors)
    # Combine subject and body to cast a wide semantic net
    search_query = f"{state['draft_subject']} {state['draft_body']}"
    
    history = vector_db.query_history(
        contact_email=recipient, 
        query_text=search_query, 
        k=5
    )
    
    print(f"   -> Found Persona: {'Yes' if persona else 'No'}")
    print(f"   -> Found Raw Emails: {len(history)}")
        
    return {
        "target_persona": persona,
        "historical_emails": history
    }

def evaluation_node(state: ProtectionState) -> ProtectionState:
    """The Brain: Compares the draft to Persona + Raw History."""
    print("🧠 [Agent]: Evaluating draft against hybrid memory...")
    
    # Format the top 5 historical emails into a readable string
    history_text = "No relevant prior emails found."
    if state["historical_emails"]:
        history_text = ""
        for i, doc in enumerate(state["historical_emails"]):
            # Pulling from the metadata structure we built earlier
            subj = doc.metadata.get("subject", "Unknown")
            date = doc.metadata.get("date", "Unknown")
            atts = doc.metadata.get("attachments", "None")
            # Clipping the body to save tokens while keeping context
            body_snippet = doc.page_content[:300] 
            
            history_text += f"\n--- PAST EMAIL {i+1} ---\n"
            history_text += f"Date: {date}\nSubject: {subj}\nAttachments: {atts}\n"
            history_text += f"Body Snippet: {body_snippet}...\n"

    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(SecurityVerdict)
    
    prompt = f"""
    You are an AI Security Advisor embedded in an email client. Your job is to prevent misdirected emails.
    
    Evaluate the following outgoing draft against the recipient's historical baseline.
    
    === BASELINE: RECIPIENT PERSONA (Summary) ===
    {state['target_persona'] if state['target_persona'] else "No verified persona exists."}
    
    === BASELINE: RELEVANT PAST EMAILS (Top 5 matches) ===
    {history_text}
    
    === OUTGOING DRAFT ===
    To: {state['draft_recipient']}
    Subject: {state['draft_subject']}
    Body: {state['draft_body']}
    Attachments: {', '.join(state['draft_attachments']) if state['draft_attachments'] else 'None'}
    
    INSTRUCTIONS:
    1. Check for Contradictions: Does the draft reference topics, attachments, or companies that severely clash with BOTH the Persona summary and the Past Emails?
    2. Missing Context is Suspicious: If the draft is highly technical or sensitive (e.g., budget sheets) but the Past Emails are strictly casual or about a different project, flag it.
    3. Calculate a risk_score (0-100).
    4. If the risk is high enough to warrant a user alert, set status to WARN. Otherwise, SAFE.
    5. Write a helpful 'reasoning' message explaining the mismatch (e.g., "You attached Q4 Budget, but past emails with Joe only discuss Marketing.").

    OUTPUT FORMAT:
    Write a highly concise 'reasoning' block. Do NOT write paragraphs. 
    Use exactly 2-3 short, punchy bullet points detailing the specific anomalies or risks found. 
    Each bullet should be under 15 words.
    Order them by importance based on your opinion.
    
    Example format:
    * Topic mismatch: Draft discusses 'Financial Report', historical baseline is entirely casual.
    * Entity conflict: 'Media Budget' mentions conflict with known 'Work' persona.
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
    # Simulate drafting an email to Robert, but accidentally 
    # talking about a completely different project (e.g., TechStars).
    live_draft = {
        "draft_recipient": "robert@global-vector-dynamics.com",
        "draft_subject": "TechStars Q4 Marketing Reallocation",
        "draft_body": "Hi Robert, please review the attached TechStars marketing spend. We need to cut the ad budget by 15%.",
        "draft_attachments": ["TechStars_Budget_v2.pdf"]
    }
    
    print("\n" + "="*50)
    print("USER CLICKS 'SEND'")
    print("="*50 + "\n")
    
    final_state = protection_app.invoke(live_draft)
    verdict = final_state["verdict"]
    
    # ------------------------
    # Simulating the UI Logic
    # ------------------------
    if verdict.status == "SAFE":
        print("✅ Email sent successfully.")
    
    elif verdict.status == "WARN":
        print("\n⚠️  [UI POPUP TRIGGERED]  ⚠️")
        print(f"Risk Score: {verdict.risk_score}/100")
        print(f"Agent Reasoning: \n{verdict.reasoning}")
        print(f"Flagged Topics: {verdict.flagged_context}")
        print("-" * 30)
        
        # Simulating the user's buttons
        user_choice = input("Do you want to (1) Send Anyway or (2) Back to Editing? [1/2]: ")
        
        if user_choice == "1":
            print("\n🚀 Overriding alert. Email sent.")
        else:
            print("\n✏️ Returning to draft...")

