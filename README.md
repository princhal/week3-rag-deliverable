# Week 3 RAG Demo — Full Stack

A full-stack demo app built with **Python FastAPI** (backend) and **Next.js** (frontend).

## Project Structure

```
Deliverable/
├── backend/
│   ├── main.py           # FastAPI app
│   └── requirements.txt  # Python dependencies
├── frontend/             # Next.js app
├── run.sh                # One-command startup script
└── rag_system/           # Existing RAG implementation
```

## Quick Start

```bash
# From the Deliverable/ folder — starts both servers with one command
./run.sh
```

Then open your browser:
- **Frontend UI** → http://localhost:3000
- **API Docs (Swagger)** → http://localhost:8000/docs

## Run Separately

```bash
# Backend
pip3 install -r backend/requirements.txt
python3 -m uvicorn backend.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm run dev
```
