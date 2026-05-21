import time
from src.agents.protection_graph import protection_app
from src.agents.ingestion_graph import ingestion_app

def simulate_email_client():
    print("="*50)
    print("✉️  MOCK EMAIL CLIENT STARTED")
    print("="*50)
    
    # The user writes a draft
    live_draft = {
        "draft_recipient": "robert@global-vector-dynamics.com",
        "draft_subject": "TechStars Q4 Marketing Reallocation",
        "draft_body": "Hi Robert, please review the attached TechStars marketing spend. We need to cut the ad budget by 15%.",
        "draft_attachments": ["TechStars_Budget_v2.pdf"]
    }
    
    print(f"\nUser clicks 'Send' to: {live_draft['draft_recipient']}...")
    
    print("\n--- 🛡️ TRIGGERING GATEKEEPER ---")
    final_protection_state = protection_app.invoke(live_draft)
    verdict = final_protection_state["verdict"]
    
    if verdict.status == "SAFE":
        print("\n✅ [UI]: Email sent successfully.")
        send_and_learn(live_draft)
        
    elif verdict.status == "WARN":
        print("\n⚠️  [UI POPUP TRIGGERED]  ⚠️")
        print(f"Risk Score: {verdict.risk_score}/100")
        print(f"Alert: {verdict.reasoning}")
        print(f"Flagged Topics: {verdict.flagged_context}")
        print("-" * 30)
        
        # Simulating the user's decision
        user_choice = input("\nDo you want to (1) Send Anyway or (2) Back to Editing? [1/2]: ")
        
        if user_choice == "1":
            print("\n🚀 [UI]: Overriding alert. Email sent.")
            send_and_learn(live_draft)
        else:
            print("\n✏️ [UI]: Returning to draft...")

def send_and_learn(draft: dict):
    """Simulates sending the email, then updates the AI's memory."""
    time.sleep(1) 
    
    print("\n--- 🧠 TRIGGERING BACKGROUND LEARNING ---")
    ingestion_app.invoke({"live_email_dict": draft})
    print("\n✅ Memory Agent has updated the Persona!")

if __name__ == "__main__":
    simulate_email_client()