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
    # Launch the store
    store = PersonaStore()
    
    # Create a mock Persona dictionary (matching the Pydantic schema structure)
    mock_persona = {
        "email": "lewis@amazon.com",
        "inferred_name": "Lewis Chao",
        "company": "Amazon",
        "job_title": "CFO",
        "relationship_to_sender": "Client",
        "known_topics": ["Q3 Budget", "Project Phoenix"],
        "last_updated": "2026-05-17",
        "last_talked": "2026-05-17"
    }
    
    print("Testing Save...")
    store.upsert_persona(mock_persona)
    
    print("\nTesting Retrieval...")
    retrieved = store.get_persona("lewis@amazon.com")
    print(retrieved)