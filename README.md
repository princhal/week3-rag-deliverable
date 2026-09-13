# Week 3 RAG Demo

A full-stack RAG demo built with **Python FastAPI** and **Next.js**. The frontend provides query, chunk, evaluation, and embedding statistics views backed by the API.

## Project Structure

```
Deliverable/
├── backend/
│   ├── main.py           # FastAPI routes
│   ├── embed_runtime.py  # Serverless query embedding runtime
│   └── requirements.txt  # Backend dependencies
├── frontend/             # Next.js application
├── rag_system/           # Data pipeline and source RAG implementation
├── .github/workflows/    # GitHub Actions CI/CD
└── run.sh                # One-command local startup
```

## Quick Start

```bash
# From the Deliverable/ folder — starts both servers with one command
./run.sh
```

Then open your browser:
- **Frontend UI** → http://localhost:3000
- **API Docs (Swagger)** → http://localhost:8000/docs

## Production

- **Frontend:** https://deliverable-frontend.vercel.app
- **Backend:** https://deliverable-backend.vercel.app

The backend exposes these primary endpoints:

- `GET /api/hello` — health check
- `GET /api/stats` — chunk and embedding statistics
- `GET /api/chunks` — chunk data grouped by strategy
- `GET /api/results` — evaluation results
- `POST /api/query` — live retrieval query

## GitHub Actions and Vercel

The workflow in `.github/workflows/ci-cd.yml` runs frontend lint/build and backend Python validation on pull requests and pushes. A push to `main` deploys both services to Vercel after validation passes. The latest workflow run passed: https://github.com/princhal/week3-rag-deliverable/actions/runs/34766745158

Add this repository secret in GitHub:

- `VERCEL_TOKEN`

Create a Vercel token from the Vercel account settings. Project IDs are available with `vercel project inspect <project-name>`.

## Environment Variables

For live Supabase-backed queries, configure these variables in the backend environment. Keep service keys out of Git and frontend code:

```dotenv
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=your-service-role-key
```

The frontend uses `NEXT_PUBLIC_API_URL` in production and defaults to `http://localhost:8000` locally.

## Run Separately

```bash
# Backend
pip3 install -r backend/requirements.txt
python3 -m uvicorn backend.main:app --reload --port 8000

# Frontend (new terminal)
cd frontend
npm run dev
```
