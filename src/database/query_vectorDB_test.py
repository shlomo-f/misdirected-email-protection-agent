import os
from dotenv import load_dotenv
from src.database.vector_store import EmailVectorStore

load_dotenv()

def print_retrieval_results(title, results):
    print(f"\n--- 📤 RETRIEVAL RESULTS: {title} ---")
    if not results:
        print("❌ No matching historical emails found for this scope.")
    else:
        print(f"✅ Found {len(results)} matching document(s):\n")
        for i, doc in enumerate(results):
            subject = doc.metadata.get("subject", "No Subject")
            date = doc.metadata.get("date", "Unknown Date")
            attachments = doc.metadata.get("attachments", "None")
            contact = doc.metadata.get("contact_email", "Unknown Contact")
            
            print(f"[Match #{i+1}]")
            print(f"   🔹 To/From Contact: {contact}")
            print(f"   🔹 Subject: {subject}")
            print(f"   🔹 Date: {date}")
            print(f"   🔹 Attachments: {attachments}")
            print(f"   🔹 Content Snippet: {doc.page_content[:150].strip()}...")
            print("-" * 40)

def test_query_transformation():
    print("=" * 60)
    target_contact = "joe@fluxpoint-il.com"
    print(f"🧪 TESTING QUERY TRANSFORMATION FOR: {target_contact}")
    print("=" * 60)

    try:
        vector_db = EmailVectorStore()
    except Exception as e:
        print(f"❌ Failed to initialize Vector Store: {e}")
        return

    noisy_draft_text = (
        "Hey Joe! Hope you're doing awesome man. Did you see the match last night? "
        "Total madness at the end there! Anyway, I was thinking about what we talked about "
        "regarding the cloud compute costs and budgeting constraints for the new vector databases "
        "on the Agentic AI trading platform infrastructure proposal. Let me know if you want "
        "to catch up for lunch this week or grab coffee. Talk soon!"
    )

    print("\n--- 📥 INPUT NOISY DRAFT CONTENT ---")
    print(noisy_draft_text)
    print("-" * 60)

    # 1. Run & Print Local Context History
    print("\n--- ⚙️ EXECUTING QUERY_HISTORY (Targeted Filter) ---")
    history_results = vector_db.query_history(
        contact_email=target_contact,
        query_text=noisy_draft_text,
        k=3
    )
    print_retrieval_results(f"Targeted History ({target_contact})", history_results)

    # 2. Run & Print Cross-Recipient Global Context History
    print("\n--- ⚙️ EXECUTING QUERY_HISTORY_GLOBAL (Cross-Recipient) ---")
    global_results = vector_db.query_history_global(
        query_text=noisy_draft_text,
        k=3
    )
    print_retrieval_results("Global Cross-Recipient History", global_results)

if __name__ == "__main__":
    test_query_transformation()