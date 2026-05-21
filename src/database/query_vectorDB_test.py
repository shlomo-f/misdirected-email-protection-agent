# src/database/query_vectorDB_test.py
import os
from dotenv import load_dotenv
from src.database.vector_store import EmailVectorStore

load_dotenv()

def test_query_transformation():
    print("=" * 60)
    # Using Joe's email as the fixed contact baseline
    target_contact = "joe@fluxpoint-il.com"
    
    print(f"🧪 TESTING QUERY TRANSFORMATION FOR: {target_contact}")
    print("=" * 60)

    # Initialize the Vector Store
    try:
        vector_db = EmailVectorStore()
    except Exception as e:
        print(f"❌ Failed to initialize Vector Store: {e}")
        return

    # Simulate a highly diluted draft full of conversational noise
    noisy_draft_text = (
        "Hey Joe! Hope you're doing awesome man. Did you see the match last night? "
        "Total madness at the end there! Anyway, I was thinking about what we talked about "
        "regarding the cloud compute costs and budgeting constraints for the new vector databases "
        "on the Agentic AI trading platform infrastructure proposal. Let me know if you want "
        "to catch up for lunch this week or grab a coffee. Talk soon!"
    )

    print("\n--- 📥 INPUT NOISY DRAFT CONTENT ---")
    print(noisy_draft_text)
    print("-" * 60)

    print("\n--- ⚙️ EXECUTING QUERY_HISTORY ---")
    results = vector_db.query_history(
        contact_email=target_contact,
        query_text=noisy_draft_text,
        k=3
    )

    # Evaluate the retrieved results
    print("\n--- 📤 RETRIEVAL RESULTS FROM CHROMADB ---")
    if not results:
        print("❌ No matching historical emails found! Did you remember to ingest Joe's emails first?")
    else:
        print(f"✅ Found {len(results)} matching document(s):\n")
        for i, doc in enumerate(results):
            # Safe parsing of metadata
            subject = doc.metadata.get("subject", "No Subject")
            date = doc.metadata.get("date", "Unknown Date")
            attachments = doc.metadata.get("attachments", "None")
            
            print(f"[Match #{i+1}]")
            print(f"   🔹 Subject: {subject}")
            print(f"   🔹 Date: {date}")
            print(f"   🔹 Attachments: {attachments}")
            print(f"   🔹 Content Snippet: {doc.page_content[:150].strip()}...")
            print("-" * 40)

if __name__ == "__main__":
    test_query_transformation()