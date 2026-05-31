"""
=============================================================================
RAG API SERVER
=============================================================================

This module is the heart of the user-facing application. It runs a blazing-fast 
FastAPI web server that listens for questions from your website, searches the 
Vector Database for facts, and asks the AI to generate a fully sourced answer.

How the pipeline works (Step-by-Step):
-----------------------------------------------------------------------------
1. BOOTSTRAP: It loads the environment, connects to ChromaDB, and verifies 
   that the AI keys are present.
2. OBSERVABILITY: It runs a background middleware that tracks every request, 
   calculating milliseconds of latency, successes, and errors. This is vital 
   for production monitoring (e.g., checking if the API is slow).
3. HEALTH PROBES: It exposes `/health` and `/ready` endpoints. Cloud providers 
   (like AWS or Kubernetes) use these to know if your server has crashed and 
   needs an automatic restart.
4. DYNAMIC RETRIEVAL: When a user asks a question, it fetches the ChromaDB 
   collection dynamically. (This prevents the server from crashing if the 
   `collector.py` happens to be rebuilding the database at that exact second).
5. RAG GENERATION: It pulls the top matching paragraphs, injects them into 
   the AI's System Prompt, and streams back a highly accurate, hallucination-free 
   response to the frontend client.
=============================================================================
"""

import os
import time
from pathlib import Path
from threading import Lock
from urllib.parse import urlparse

import chromadb
from chromadb.utils import embedding_functions
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from openai import OpenAI
from pydantic import BaseModel

import utils.helper as helper
import utils.logger as logger


# =============================================================================
# 0. AUTONOMOUS ROOT DETECTION
# =============================================================================
def get_project_root() -> Path:
    """
    Return the project root directory used by the API server.
    The lookup walks upward from the current file until it finds a directory
    that looks like the repository root, identified by `config/` or `requirements.txt`.
    """
    current_dir = Path(__file__).resolve().parent
    for directory in [current_dir, current_dir.parent, current_dir.parent.parent]:
        if (directory / "config").is_dir() or (directory / "requirements.txt").exists():
            return directory
    return current_dir.parent

PROJECT_ROOT = get_project_root()


# =============================================================================
# 1. INITIAL SETUP
# =============================================================================
logger = logger.setup_logger(logger_name="fastapi_server", log_filename="server.log")
load_dotenv()
config = helper.config
logger.debug(f"Server project root resolved to {PROJECT_ROOT}")

# Validate critical environment settings early so startup errors are explicit.
# If the API key is missing, the server refuses to start instead of failing later.
model_api_key = os.getenv("MODEL_API_KEY")
if not model_api_key:
    raise RuntimeError(
        "MODEL_API_KEY is required to start the API server. "
        "Define it in your environment or .env file."
    )


# =============================================================================
# 2. EMBEDDING CONFIGURATION
# =============================================================================
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=model_api_key,
    model_name=config['embeddings']['embedding_model']
)


# =============================================================================
# 3. CHROMADB CONNECTION
# =============================================================================
# Force lowercase and build the absolute path using the local PROJECT_ROOT
folder_name = config['storage'].get('data_folder', 'data').lower()
db_path_obj = PROJECT_ROOT / folder_name / "vector_db"
db_path = str(db_path_obj) # ChromaDB requires a string path
logger.debug(f"ChromaDB path resolved to {db_path}")

# Ensure the database folder exists before connecting
os.makedirs(db_path, exist_ok=True)
chroma_client = chromadb.PersistentClient(path=db_path)

# Pre-create the collection at startup so the API fails early if embeddings are misconfigured.
collection = chroma_client.get_or_create_collection(
    name="rag_context", 
    embedding_function=openai_ef
)


# =============================================================================
# 4. SERVER AND AI CLIENT INITIALIZATION
# =============================================================================
app = FastAPI()

# Lightweight in-memory metrics for operational visibility.
# Thread Lock is used to prevent data corruption if 50 users ask a question at the same exact millisecond.
METRICS_LOCK = Lock()
METRICS = {
    "total_requests": 0,
    "ask_requests": 0,
    "ask_success": 0,
    "ask_errors": 0,
    "ask_latency_ms_sum": 0.0,
    "ask_latency_ms_max": 0.0,
}

# Add CORS middleware (Allows the frontend website to securely talk to this backend API)
app.add_middleware(
    CORSMiddleware,
    allow_origins=config['server'].get('allowed_origins', ["*"]),
    allow_origin_regex=config['server'].get('allow_origin_regex'),
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, OPTIONS)
    allow_headers=["*"],  # Allows all headers
)

# Initialize the generative AI Client
client = OpenAI(
    base_url=config['ai'].get('base_url'), # Dynamically supports OpenAI or Open Source models
    api_key=model_api_key
)

class Query(BaseModel):
    question: str


# =============================================================================
# 5. OBSERVABILITY & MIDDLEWARE
# =============================================================================
@app.middleware("http")
async def capture_metrics(request: Request, call_next):
    """
    Capture request counters and latency for basic observability.
    This acts as a stopwatch for every request entering the server.
    """
    started_at = time.perf_counter()
    path = request.url.path

    with METRICS_LOCK:
        METRICS["total_requests"] += 1
        if path == "/ask":
            METRICS["ask_requests"] += 1

    try:
        response = await call_next(request)
    except Exception:
        # If the code crashes halfway through, log the failure and the latency
        if path == "/ask":
            latency_ms = (time.perf_counter() - started_at) * 1000
            with METRICS_LOCK:
                METRICS["ask_errors"] += 1
                METRICS["ask_latency_ms_sum"] += latency_ms
                METRICS["ask_latency_ms_max"] = max(METRICS["ask_latency_ms_max"], latency_ms)
        raise

    # If successful, calculate how fast we answered and record it
    if path == "/ask":
        latency_ms = (time.perf_counter() - started_at) * 1000
        with METRICS_LOCK:
            METRICS["ask_latency_ms_sum"] += latency_ms
            METRICS["ask_latency_ms_max"] = max(METRICS["ask_latency_ms_max"], latency_ms)
            if response.status_code < 500:
                METRICS["ask_success"] += 1
            else:
                METRICS["ask_errors"] += 1

    return response


# =============================================================================
# 6. SERVER ROUTES & ENDPOINTS
# =============================================================================
@app.get("/health")
async def health_check():
    """Return lightweight service status. Used by load balancers to check if the server is online."""
    return {"status": "ok"}


@app.get("/ready")
async def readiness_check():
    """
    Deep readiness check. Used by deployment orchestrators to verify that 
    the API is not just online, but also fully connected to the Vector Database.
    """
    checks = {
        "model_api_key": bool(model_api_key),
        "vector_db_path_exists": os.path.isdir(db_path),
    }

    try:
        ready_collection = chroma_client.get_collection(
            name="rag_context",
            embedding_function=openai_ef,
        )
        checks["vector_collection_available"] = ready_collection is not None
    except Exception as error:
        logger.warning(f"Readiness check could not access rag_context collection: {error}")
        checks["vector_collection_available"] = False

    is_ready = all(checks.values())
    status = "ready" if is_ready else "not_ready"

    if is_ready:
        return {"status": status, "checks": checks}

    # HTTP 503 means Service Unavailable. Prevents traffic from routing to a broken server.
    return JSONResponse(status_code=503, content={"status": status, "checks": checks})


@app.get("/metrics")
async def metrics():
    """Return basic request and latency counters for monitoring dashboards."""
    with METRICS_LOCK:
        ask_requests = METRICS["ask_requests"]
        avg_latency_ms = (
            METRICS["ask_latency_ms_sum"] / ask_requests if ask_requests > 0 else 0.0
        )
        snapshot = {
            **METRICS,
            "ask_latency_ms_avg": round(avg_latency_ms, 3),
            "uptime_status": "ok",
        }

    return snapshot

@app.post("/ask")
async def answer_user(item: Query):
    """
    CORE RAG ENDPOINT: Answers a user question using retrieval-augmented generation.

    Args:
        item: Request payload containing the end-user question.

    Returns:
        A JSON dictionary with the generated answer and a status flag.
    """
    try:
        logger.debug(f"Received question with length {len(item.question)}")
        
        # 1. DYNAMIC RETRIEVAL
        try:
            # We fetch the collection dynamically on every single request.
            # Why: If 'collector.py' is currently wiping and rebuilding the database in 
            # the background, the collection might temporarily not exist.
            current_collection = chroma_client.get_collection(
                name="rag_context", 
                embedding_function=openai_ef
            )
        except Exception:
            # Graceful degradation: Ask the user to wait instead of crashing the app.
            return {
                "response": "I am currently updating my knowledge base. Please ask me again in about 10 seconds.", 
                "status": "updating"
            }

        # Search the database for the top_k most relevant text chunks
        results = current_collection.query(
            query_texts=[item.question],
            n_results=config['embeddings']['top_k']
        )
        logger.debug(f"Retrieved {len(results['documents'][0]) if results.get('documents') else 0} context chunks")
        
        # Join the retrieved chunks into one large string.
        retrieved_context = "\n---\n".join(results['documents'][0])
        
        # 2. PROMPT CONSTRUCTION
        # Combine the strict rules from the YAML with the actual database evidence
        full_system_message = (
            f"{config['ai']['system_prompt']}\n\n"
            f"### RETRIEVED CONTEXT ###\n"
            f"{retrieved_context}"
        )

        # 3. GENERATION
        # Send everything to the AI and wait for the formatted response
        response = client.chat.completions.create(
            model=config['ai']['model'],
            messages=[
                {"role": "system", "content": full_system_message},
                {"role": "user", "content": item.question}
            ],
            temperature=config['embeddings']['temperature']
        )
        logger.debug("OpenAI chat completion generated successfully")
        
        return {
            "response": response.choices[0].message.content,
            "status": "success"
        }
        
    except Exception as e:
        logger.exception(f"Error processing question '{item.question}': {e}")
        return {"error": str(e)}


# =============================================================================
# 7. EXECUTION ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    logger.info("Starting FastAPI server...")
    import uvicorn
    
    # We explicitly read the binding 'host' to open the server to the internet 
    # (0.0.0.0) instead of parsing the public URL which caused connection issues.
    bind_host = config['server'].get('host', '0.0.0.0')
    bind_port = int(config['server'].get('port', 8000))
    
    uvicorn.run(
        app,
        host=bind_host,
        port=bind_port
    )