# 🛡️ AI Outbound Email Gatekeeper & DLP Agent

An intelligent Data Loss Prevention (DLP) system and email gatekeeper that intercepts misdirected emails, evaluates outbound communication safety using hybrid memory, and implements a continuous learning loop from human overrides. Built in Python using LangGraph, ChromaDB, and Streamlit.

---

## 📌 The Problem
"Silent Breaches" happen when an email is accidentally addressed to the wrong person due to autocomplete errors or identical first names, leaking corporate assets, project specifications, or sensitive financials (e.g., intending to email 'Joe at Company X' but mistakenly sending a sensitive attachment to 'Joe at Company Y'). Traditional DLP systems rely on rigid regex or domain rules that fail to catch these contextual, human-error mismatches.

## 🧠 System Architecture & Core Features

This system separates the evaluation and learning layers into two distinct, deterministic state machines using **LangGraph**:

1. **The Gatekeeper Graph (Protection):** Intercepts outbound email drafts and evaluates them against historical communication context before delivery.
2. **The Ingestion Graph (Continuous Learning):** Processes incoming inboxes or handles real-time human overrides to dynamically adapt the agent's baseline knowledge.

```text
[Outbound Draft] ──> [Gatekeeper Graph] ──(Semantic Match?)──> [SAFE: Send]
                                │
                        (Anomaly Detected)
                                │
                                └──> [WARNING: Block & Alert User]
                                              │
                                      (User Overrides)
                                              │
                                              └──> [Ingestion Graph] ──> [Mutate Recipient Profile]
```

### 🗝️ Key Engineering Highlights
* **Hybrid Memory Architecture:** Combines **Episodic Memory** (ChromaDB vector store tracking raw semantic history) with **Entity Memory** (TinyDB document store tracking high-level persona summaries, known topics, and relationship baselines) to make comprehensive safety evaluations.
* **Query Transformation (DLP Optimization):** Implements an upstream `gpt-4o-mini` translation node to strip conversational noise (pleasantries, casual chat) out of outbound drafts, extracting high-density keyword vectors to query ChromaDB. This eliminates *Semantic Dilution* and cuts token consumption.
* **Human-in-the-Loop Override & Adaptive Ingestion:** When a user overrides an AI warning, the system routes the draft through a background memory engine that modifies the recipient's Entity Persona schema, ensuring the agent dynamically adapts to context shifts.

---

## 🛠️ Tech Stack
* **Orchestration:** LangGraph (StateGraph, State Dicts)
* **LLMs:** OpenAI (GPT-4o for structured safety evaluations, GPT-4o-Mini for query transformation)
* **Vector Database:** ChromaDB (Local persistence)
* **Structured Database:** TinyDB (Local JSON persistence)
* **UI Dashboard:** Streamlit

---

## 🚀 Getting Started

### 1. Prerequisites & Installation
Clone the repository and install the dependencies inside a virtual environment:

```bash
git clone https://github.com/shlomo-f/misdirected-email-protection-agent.git
cd misdirected-email-protection-agent

# Set up virtual environment
python -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 2. Environment Configuration

Create a `.env` file in the root directory and add your OpenAI API Key:

```env
OPENAI_API_KEY=your_actual_api_key_here
```

### 3. Running the App
Launch the interactive Streamlit dashboard to test the engine:

```bash
streamlit run app.py
```
## 🎮 How to Test the Demo Loop (Mock Inbox)

* **Phase 1 (Agent Memory Ingestion):** You will be presented with two onboarding training flows to initialize the agent's memory layers:
  * **Option A (Live Document Processing):** Drag and drop individual `.eml` files directly into the Streamlit file uploader. The application generates a runtime virtual file buffer, vectorizes the documents, and purges the raw assets immediately post-ingestion.
  * **Option B (Programmatic Local Batch Ingestion):** Click **"Load All Local Emails"**. The backend dynamically scans the internal filesystem (`data/raw_emails/`), executes an automated iterative loop, indexes the historical message context into ChromaDB, and updates the contact schemas inside TinyDB.
* **Phase 2 (DLP Contextual Interception):** Navigate to the composed email client and submit a sensitive draft. Because the draft discusses corporate project constraints or architecture specifications foreign to the recipient's baseline profile, the **Agent Terminal** will compute a semantic clash, issue a defensive warning state, and expose the specific risk reasoning.
* **Phase 3 (Continuous Adaptation Feedback Loop):** Click **"Override & Send Anyway"**. This action explicitly bypasses the warning, routes the content directly back through the background ingestion graph, and mutates the contact's Persona Document on disk. Re-evaluating the exact same draft immediately afterward results in a **SAFE** verdict—proving the engineering loops successfully capture real-time context drifts.

https://github.com/user-attachments/assets/65fa4b77-dc8f-48f0-8070-7b8fcd5ddd88

## 🗺️ Production Roadmap
* **Deep Attachment Inspection:** Transition from metadata-only attachment tracking to full binary parsing (extracting raw text from `.pdf`, `.docx`, and `.xlsx` payloads) using deep-inspection pipelines.
* **Risk-Score Calibration:** Incorporate enterprise-specific risk weights based on classification tags (e.g., `CONFIDENTIAL`, `INTERNAL ONLY`).
* **Native Client Integrations (Gmail Workspace Add-on / Outlook VSTO Add-in):** Transition from a demo to a client extension. Intercept outbound drafts directly within the user's native email client using real-time API triggers before the `Send` event completes
* **Hybrid & Private LLM Deployment Options:** Add support for hosting open-source foundation models (e.g., Llama 3, Mistral) within the enterprise perimeter or secure platforms like IBM watsonx, allowing organizations with strict data-privacy mandates to bypass external APIs entirely.
