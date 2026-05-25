import os
from tinydb import TinyDB, Query

class PersonaStore:
    def __init__(self):
        self.db_path = "data/personas/personas.json"
        
        # Ensure the folder exists (safety check)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize the database
        self.db = TinyDB(self.db_path, indent=4) # indent=4 makes the JSON human-readable!
        self.User = Query()

    def upsert_persona(self, persona_dict: dict):
        """
        Saves a new persona or updates an existing one based on the email address.
        """
        email = persona_dict.get('email')
        if not email:
            raise ValueError("Persona dictionary must contain an 'email' key.")
            
        # Upsert: Update if the email exists, Insert if it doesn't
        self.db.upsert(persona_dict, self.User.email == email)

        print(f"✅ Persona saved for: {email}")
    
    def search_by_name_or_prefix(self, prefix: str) -> list[dict]:
        """
        Searches personas where the email prefix or inferred names 
        contain the search prefix (e.g., 'robert' matches 'robert@global-energy.com').
        """
        self.db.clear_cache()
        prefix_clean = prefix.lower().strip()
        
        def match_condition(doc):
            # Check email prefix
            doc_email = doc.get("email", "").lower()
            doc_prefix = doc_email.split("@")[0] if "@" in doc_email else ""
            if prefix_clean in doc_prefix:
                return True
                
            # Check inferred names list
            names = doc.get("inferred_names", [])
            if isinstance(names, str):
                names = [names]
            if any(prefix_clean in name.lower() for name in names):
                return True
                
            return False

        return self.db.search(match_condition)

    def get_persona(self, email: str) -> dict:
        """
        Retrieves a persona by email, forcing a fresh read from disk.
        Returns None if not found.
        """
        self.db.clear_cache()
        
        results = self.db.search(self.User.email == email)
        
        # Return the first match or None
        return results[0] if results else None

# --- Test Script ---
if __name__ == "__main__":
    store = PersonaStore()
    
    lewis_amazon = {
        "email": "lewis@amazon.com",
        "inferred_names": ["Lewis Chao"], 
        "company": "Amazon",
        "job_title": "CFO",
        "relationship_to_sender": "Client",
        "known_topics": ["Q3 Budget"],
        "last_updated": "2026-05-17",
        "last_talked": "2026-05-17"
    }
    
    lewis_house = {
        "email": "lewis.bill@house-set-solutions.com",
        "inferred_names": ["Lewis Bill"],   
        "company": "House Set Solutions",
        "job_title": "CEO",
        "relationship_to_sender": "Prospect",
        "known_topics": ["Real Estate Strategy"],
        "last_updated": "2026-05-25",
        "last_talked": "2026-05-25"
    }
    
    print("Saving personas...")
    store.upsert_persona(lewis_amazon)
    store.upsert_persona(lewis_house)
    
    # Test Prefix Search
    print("\n--- Testing Search for 'lew' ---")
    results_lew = store.search_by_name_or_prefix("lew")
    print(f"Found {len(results_lew)} results:")
    for doc in results_lew:
        print(f"- {doc['email']} ({doc.get('company')})")
        
    print("\n--- Testing Search for 'l' ---")
    results_l = store.search_by_name_or_prefix("l")
    print(f"Found {len(results_l)} results:")
    for doc in results_l:
        print(f"- {doc['email']} ({doc.get('company')})")
    