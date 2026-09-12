from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

app = FastAPI(title="RAG Demo API", version="1.0.0")

# Allow Next.js dev server to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "service": "RAG Demo API"}


@app.get("/api/hello")
async def hello() -> JSONResponse:
    """Demo endpoint – replace with your actual RAG logic."""
    return JSONResponse(
        content={
            "message": "Hello from FastAPI! 🚀",
            "data": [1, 2, 3],
        }
    )
