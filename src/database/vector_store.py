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
            persist_directory=self.persist_directory,
            collection_metadata={"hnsw:space": "cosine"}
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

    def _clean_email_address(self, email_str: str) -> str:
        """NEW: Extracts clean 'user@domain.com' from display headers for robust filtering."""
        _, addr = parseaddr(email_str)
        return addr.lower().strip()

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
          
        clean_recipient = self._clean_email_address(parsed_email['contact_email'])

        # Create a LangChain Document
        doc = Document(
            page_content=parsed_email['body'],
            metadata={
                "subject": parsed_email['subject'],
                "contact_name": parsed_email['contact_name'],
                "contact_email": clean_recipient,
                "contact_domain": self._extract_domain(clean_recipient),
                "date": str(parsed_email['date']),
                "attachments": attachments_str,
                "has_attachments": bool(filenames)
            }
        )

        # Save to disk
        self.vector_db.add_documents(documents=[doc], ids=[email_id])
        print(f"✅ Processed email: '{parsed_email['subject']}' (ID: {email_id}) (to: {clean_recipient})")
    
    def _optimize_query(self, query_text: str) -> str:
        """Helper to clean query strings and eliminate semantic dilution."""
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
        response = transformer_llm.invoke(transform_prompt)
        return response.content.strip()

    def query_history(self, contact_email: str, query_text: str, k: int = 5):
        """
        Retrieves the most relevant past emails for a specific contact.
        Optimizes the search query using an LLM to avoid semantic dilution.
        """
        print("   🔮 [Vector Store]: Optimizing search query via transformation...")
        clean_email = self._clean_email_address(contact_email)
        optimized_keywords = self._optimize_query(query_text)
        
        print(f"      -> Original text length: {len(query_text)} chars")
        print(f"      -> Optimized search query: '{optimized_keywords}'")
        
        # Pass the high-density keywords to ChromaDB instead of the raw email
        results = self.vector_db.similarity_search(
            optimized_keywords,
            k=k,
            filter={"contact_email": clean_email}
        )
        return results

    def query_history_global(self, query_text: str, k: int = 3, score_threshold: float = 0.3):
        """
        Performs a cross-recipient global semantic check.
        Only returns documents that meet or exceed the semantic score_threshold.
        """
        print("   🔮 [Vector Store]: Running cross-recipient global semantic check...")
        optimized_keywords = self._optimize_query(query_text)
        
        # Fetch documents along with their similarity scores
        results_with_scores = self.vector_db.similarity_search_with_relevance_scores(
            optimized_keywords,
            k=k
        )
        
        # Filter out items below the acceptable threshold
        relevant_docs = []
        for doc, score in results_with_scores:
            print(f"      -> Candidate Match: '{doc.metadata.get('subject')}' | Semantic Score: {score:.4f}")
            if score >= score_threshold:
                relevant_docs.append(doc)
            else:
                print(f"         [Dropped]: Score below threshold ({score_threshold})")
                
        print(f"   📊 Global check returned {len(relevant_docs)}/ {k} requested documents.")
        return relevant_docs

# --- Test Script ---
if __name__ == "__main__":
    store = EmailVectorStore()
    
    test_emails = [
        r"data\raw_emails\Email thread - HazeYam - Real Estate Platform Launch.eml",
        r"data\raw_emails\Inbound - Infrastructure Proposal – Agentic AI Trading Platform.eml",
        r"data\raw_emails\Project Aegis - IAM Architecture & Deepfake Mitigation Rollout 2026-05-18T18_10_16+03_00.eml",
        r"data\raw_emails\Robert 1 - Q3 Budget Draft & Hiring Update - Project Phoenix 2026-05-10T09_45_32+03_00.eml",
        r"data\raw_emails\Robert 2 - NY Clean-Gen Plant - Architecture & Compliance Review 2026-05-24T19_03_09+03_00.eml",
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
            print(f"  key: {value}")
            
        # The Raw Text
        print(f"\n[TEXT BODY]:")
        print(f"  {db_content['documents'][i][:100]}...")
        
        vector_preview = db_content['embeddings'][i][:5]
        print(f"\n[VECTOR PREVIEW (First 5 of 1536)]: ")
        print(f"  {vector_preview}")
        print(f"{'='*50}")

    simulated_draft_subject = "TNY Clean-Gen - Quick IAM Question"
    simulated_draft_body = (
        "Hi Robert,\n\nFollowing up on the NERC-CIP requirements, could you loop in your Identity Security lead? "
        "We need to quickly align on the IAM and access control setup for the plant operators before Thursday's call.\n\nBest,\nJoe"
    )
    
    test_query = f"{simulated_draft_subject} {simulated_draft_body}"
    print(f"\n🔍 Running general test query: '{test_query}'...")
    
    search_results = store.query_history_global(query_text=test_query, k=5)
    
    print(f"\n🎯 [SEARCH RESULTS] Found {len(search_results)} relevant emails:")
    for index, match in enumerate(search_results, start=1):
        print(f"\n  [{index}] Match Subject: {match.metadata.get('subject')}")
        print(f"      Contact Email: {match.metadata.get('contact_email')}")
        print(f"      Snippet: {match.page_content[:150]}...")
    print(f"\n{'='*50}")
    # ---------------------------------------------

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