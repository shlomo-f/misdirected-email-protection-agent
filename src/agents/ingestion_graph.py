import os
from typing import TypedDict, Optional
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from langchain_openai import ChatOpenAI
from src.agents.schemas import Persona
from src.database.persona_store import PersonaStore
from src.ingestion.email_parser import parse_eml

load_dotenv()

persona_db = PersonaStore()

# Define the State
class IngestionState(TypedDict):
    email_file_path: Optional[str]       # Input: Path to the raw .eml file
    live_email_dict: Optional[dict]
    parsed_email: Optional[dict]        # Output of Parser
    contact_email: Optional[str]      # The target we are profiling
    existing_persona: Optional[dict]    # What TinyDB knows
    updated_persona: Optional[Persona]  # What OpenAI generates

# Define the nodes
def parse_email_node(state: IngestionState) -> IngestionState:
    print("\n[Node: Parse] Extracting email data...")
    
    # Safely pull the live draft if it exists
    live_draft = state.get("live_email_dict")
    
    if live_draft:
        print("  -> Processing live draft from UI...")
        
        target_contact = live_draft.get("draft_recipient", "Unknown")

        parsed_data = {
            "subject": live_draft["draft_subject"],
            "body": live_draft["draft_body"],
            "from": "me@myself.com", # Mock sender for the test
            "date": "2026-05-18", # Mock date
            # Recreate the attachment dictionary structure
            "attachments": [{"filename": f} for f in live_draft.get("draft_attachments", [])],
            "contact_email": target_contact,
            "contact_name": "[No Name Provided]"
        }
    else:
        print("  -> Processing raw .eml file from disk...")
        # Safely pull the file path. If both are missing, raise a clean error.
        file_path = state.get("email_file_path")
        if not file_path:
            raise ValueError("Ingestion Graph triggered without a draft or a file path!")
        
        parsed_data = parse_eml(file_path)
    
    return {
        "parsed_email": parsed_data,
        "contact_email": parsed_data.get("contact_email")
    }

def retrieve_existing_node(state: IngestionState) -> IngestionState:
    """Checks TinyDB for an existing profile."""
    print(f"[Node: Retrieve] Checking TinyDB for: {state['contact_email']}")
    
    existing = persona_db.get_persona(state["contact_email"])
    if existing:
        print("  -> Found existing profile!")
    else:
        print("  -> No profile found. This is a new contact.")
        
    return {"existing_persona": existing}

def llm_update_node(state: IngestionState) -> IngestionState:
    """Uses OpenAI to merge the old profile with the new email content."""
    print("[Node: LLM] Generating updated Persona...")
    
    llm = ChatOpenAI(model="gpt-4o", temperature=0)
    structured_llm = llm.with_structured_output(Persona)
    
    prompt = f"""
    You are an AI Memory Agent for a misdirected email protection and Data Loss Prevention system.
    Analyze this new email and update the contact's Persona Profile.
    
    Target Email Address: {state['contact_email']}
    
    --- EXISTING KNOWLEDGE ---
    {state['existing_persona'] if state['existing_persona'] else "None. This is a brand new contact."}
    
    --- NEW EMAIL CONTENT ---
    Subject: {state['parsed_email']['subject']}
    Body: {state['parsed_email']['body']}
    
    INSTRUCTIONS:
    1. Infer the person's name and company from the email address and email content.
    2. Determine their relationship to the sender.
    3. Extract a list of distinct 'known_topics' (projects, themes) discussed in this email.
    4. If there is Existing Knowledge, MERGE the new topics with the old topics. Do not delete old context!
    5. Set 'last_updated' to today's date.
    6. STRICT RULE: For the email field, you MUST copy and paste the exact string '{state['contact_email']}' verbatim. Do not alter it or infer a corporate domain.
    """
    
    new_persona = structured_llm.invoke(prompt)
    return {"updated_persona": new_persona}

def save_node(state: IngestionState) -> IngestionState:
    """Saves the final output to TinyDB."""
    print("[Node: Save] Writing to TinyDB...")
    
    # 1. Convert the Pydantic model to a standard dictionary for TinyDB
    persona_dict = state["updated_persona"].model_dump()
    
    # 2. Explicitly force the database key to be the factual email
    persona_dict["email"] = state["contact_email"]
    
    persona_db.upsert_persona(persona_dict)
    return state

workflow = StateGraph(IngestionState)

workflow.add_node("parse", parse_email_node)
workflow.add_node("retrieve", retrieve_existing_node)
workflow.add_node("update", llm_update_node)
workflow.add_node("save", save_node)

workflow.add_edge(START, "parse")
workflow.add_edge("parse", "retrieve")
workflow.add_edge("retrieve", "update")
workflow.add_edge("update", "save")
workflow.add_edge("save", END)

ingestion_app = workflow.compile()

# --- Test Script ---
if __name__ == "__main__":
    # Point to test emails
    test_files = [
        r"data\raw_emails\Q3 Budget Draft & Hiring Update - Project Phoenix 2026-05-10T09_45_32+03_00.eml"
    ]

    for test_file in test_files:
        if os.path.exists(test_file):
            print("Starting Ingestion Graph...")
            final_state = ingestion_app.invoke({"email_file_path": test_file})
            
            print("\n🎉 INGESTION COMPLETE! Here is the final Persona:")
            print(final_state["updated_persona"].model_dump_json(indent=2))
        else:
            print(f"❌ Could not find test file: {test_file}")