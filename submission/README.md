# Vitrious — Agentic Stockout Resolution System

This folder contains the complete student submission for the Vitrious (Inventra) multi-agent stockout resolution challenge.

## Quick Start

### 1. Setup Environment

Create and activate a virtual environment:

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python -m venv venv
source venv/bin/activate
```

Install dependencies:
```bash
python -m pip install -r requirements.txt
python -m pip install -r submission/requirements.txt
```

Create your `.env` file (copy from `.env.example`):
```bash
cp .env.example .env
```
Ensure `OPENAI_API_KEY` is set in the `.env` file.

### 2. Prepare Database

If you haven't already, seed the SQLite database with the provided test cases:
```bash
python database/seed.py
```

### 3. Run the System

We provide an interactive Streamlit UI that supports the human-approval interrupt natively:
```bash
streamlit run submission/app.py
```

## Running Tests

The test suite covers all 12 required acceptance scenarios plus failure paths. It uses mock LLM agents so tests are deterministic, fast, and cost nothing.

```bash
pytest submission/tests/ -v
```

## Architecture

The system uses **LangGraph** to coordinate 3 LLM agents (Investigation, Sourcing, Review) and 5 deterministic nodes (Input Validation, Draft Proposal, Prepare Approval, Revalidation, Execution). State is maintained via LangGraph's checkpointer, enabling the system to pause execution during the human approval step and resume flawlessly.

See `submission/design.md` for a complete architecture breakdown, agent charters, tool permissions, and design rationale.
