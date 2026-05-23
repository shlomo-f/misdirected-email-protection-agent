import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from langchain_core.documents import Document
from email.utils import parseaddr
from src.ingestion.email_parser import parse_eml
import hashlib

load_dotenv()

class EmailVectorStore:
    def __init__(self):
        # Initialize the Embedding Model
        self.embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
        
        self.persist_directory = os.getenv("CHROMA_DB_PATH", "data/vector_store")
        
        self.vector_db = Chroma(
            collection_name="email_history",
            embedding_function=self.embeddings,
            persist_directory=self.persist_directory
        )

    def clear_store(self):
        """
        Safely clears all collections and documents from ChromaDB 
        """
        try:
            client = self.vector_db._client
            client.delete_collection(name="email_history")
            
            # Recreate the collection so the wrapper remains valid for future operations
            self.vector_db = Chroma(
                collection_name="email_history",
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            print("✨ Vector Store collection successfully dropped and recreated.")
            return True
        except Exception as e:
            print(f"❌ Error resetting vector store collection: {e}")
            raise e

    def _extract_domain(self, email_str: str) -> str:
        """Helper to get 'company.com' from 'name <joe@company.com>'"""
        _, addr = parseaddr(email_str)
        if '@' in addr:
            return addr.split('@')[-1].lower()
        return "unknown"

    def upsert_email(self, parsed_email: dict):
        """
        Takes the dictionary from parser.py and saves it to the Vector DB.
        """
        # Fix the Attachment Error: Extract just the filenames
        attachments_raw = parsed_email.get('attachments', [])
        filenames = [att.get('filename') for att in attachments_raw if att.get('filename')]
        attachments_str = ", ".join(filenames) if filenames else ""

        # Duplicate Protection: Create a unique ID for this email
        # Combining body and date ensures the same email gets the same ID every time
        unique_string = f"{parsed_email['body']}{parsed_email['date']}"
        email_id = hashlib.md5(unique_string.encode()).hexdigest()
          
        # Create a LangChain Document
        doc = Document(
            page_content=parsed_email['body'],
            metadata={
                "subject": parsed_email['subject'],
                "contact_name": parsed_email['contact_name'],
                "contact_email": parsed_email['contact_email'],
                "contact_domain": self._extract_domain(parsed_email['contact_email']),
                "date": str(parsed_email['date']),
                "attachments": attachments_str,
                "has_attachments": bool(filenames)
            }
        )

        # Save to disk
        self.vector_db.add_documents(documents=[doc], ids=[email_id])
        print(f"✅ Processed email: '{parsed_email['subject']}' (ID: {email_id}) (to: {parsed_email['contact_email']})")
    
    def query_history(self, contact_email: str, query_text: str, k: int = 5):
        """
        Retrieves the most relevant past emails for a specific contact.
        Optimizes the search query using an LLM to avoid semantic dilution.
        """
        print("   🔮 [Vector Store]: Optimizing search query via transformation...")
        
        # Initialize a fast, cheap model for extraction
        transformer_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        
        transform_prompt = f"""
        You are an expert search query optimizer for a corporate DLP system.
        Your task is to extract only the densest keywords, project names, technical terms, 
        and company entities from the following email text. Remove all conversational noise, 
        greetings, pleasantries, and signatures.
        
        EMAIL TEXT:
        {query_text}
        
        OUTPUT FORMAT:
        Provide only a comma-separated list of the extracted keywords and entities. Do not include any other text.
        """
        
        # Generate the optimized keyword string
        response = transformer_llm.invoke(transform_prompt)
        optimized_keywords = response.content.strip()
        
        print(f"      -> Original text length: {len(query_text)} chars")
        print(f"      -> Optimized search query: '{optimized_keywords}'")
        
        # Pass the high-density keywords to ChromaDB instead of the raw email
        results = self.vector_db.similarity_search(
            optimized_keywords,
            k=k,
            filter={"contact_email": contact_email}
        )
        return results

# --- Test Script ---
if __name__ == "__main__":
    store = EmailVectorStore()
    
    test_emails = [
        r"data\raw_emails\Email thread - HazeYam - Real Estate Platform Launch.eml",
        r"data\raw_emails\Inbound - Infrastructure Proposal – Agentic AI Trading Platform.eml",
        r"data\raw_emails\Project Aegis - IAM Architecture & Deepfake Mitigation Rollout 2026-05-18T18_10_16+03_00.eml",
        r"data\raw_emails\Q3 Budget Draft & Hiring Update - Project Phoenix 2026-05-10T09_45_32+03_00.eml",
        r"data\raw_emails\Q4 Expansion - _FreshYield_ Superfarm & Retail Integration 2026-05-18T18_07_47+03_00.eml"
    ]
    
    for file_path in test_emails:
        if os.path.exists(file_path):
            print(f"\n--- Processing: {os.path.basename(file_path)} ---")
            data = parse_eml(file_path)
            store.upsert_email(data)
        else:
            print(f"❌ File not found: {file_path}")

    # Peek into the Database
    db_content = store.vector_db.get(include=["documents", "metadatas", "embeddings"])
    print(f"\n📊 Total active records remaining in DB collection: {len(db_content['ids'])}")

    for i in range(len(db_content['ids'])):
        print(f"\n{'='*50}")
        print(f"DATABASE ENTRY ID: {db_content['ids'][i]}")
        
        # The Metadata
        print(f"\n[METADATA]:")
        for key, value in db_content['metadatas'][i].items():
            print(f"  {key}: {value}")
            
        # The Raw Text
        print(f"\n[TEXT BODY]:")
        print(f"  {db_content['documents'][i][:100]}...")
        
        vector_preview = db_content['embeddings'][i][:5]
        print(f"\n[VECTOR PREVIEW (First 5 of 1536)]: ")
        print(f"  {vector_preview}")
        print(f"{'='*50}")

    choice = input("Enter your choice (1 or 2): ").strip()

    if choice == "1":
        print("\n🗑️  Resetting the database collection...")
        try:
            store.clear_store()
            db_content_after = store.vector_db.get()
            print(f"📊 Confirmed active records remaining: {len(db_content_after['ids'])}")
        except Exception as e:
            print(f"❌ [Test Failure] Could not clear collection: {e}")
    elif choice == "2":
        print("\n💾 Data retained on disk. Exiting safely.")
        db_content_after = store.vector_db.get()
        print(f"📊 Confirmed active records remaining: {len(db_content_after['ids'])}")
    else:
        print("\n⚠️  Invalid input received. Defaulting to Option 2: Retaining data.")

