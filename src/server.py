import os
from pathlib import Path
import chromadb
from chromadb.utils import embedding_functions
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
from urllib.parse import urlparse
import utils.helper as helper
import utils.logger as logger

# 0. AUTONOMOUS ROOT DETECTION
def get_project_root() -> Path:
    """Finds the project root by looking for the 'config' folder."""
    current_dir = Path(__file__).resolve().parent
    for directory in [current_dir, current_dir.parent, current_dir.parent.parent]:
        if (directory / "config").is_dir() or (directory / "requirements.txt").exists():
            return directory
    return current_dir.parent

PROJECT_ROOT = get_project_root()

# 1. INITIAL SETUP
logger = logger.setup_logger(logger_name="fastapi_server", log_filename="server.log")
load_dotenv()
config = helper.config

# 2. EMBEDDING CONFIGURATION 
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("MODEL_API_KEY"),
    model_name=config['embeddings']['embedding_model']
)

# 3. CHROMADB CONNECTION
# Force lowercase and build the absolute path using the local PROJECT_ROOT
folder_name = config['storage'].get('data_folder', 'data').lower()
db_path_obj = PROJECT_ROOT / folder_name / "vector_db"
db_path = str(db_path_obj) # ChromaDB requires a string

# Ensure the database folder exists before connecting
os.makedirs(db_path, exist_ok=True)
chroma_client = chromadb.PersistentClient(path=db_path)

# Retrieve the collection
collection = chroma_client.get_or_create_collection(
    name="rag_context", 
    embedding_function=openai_ef
)

# 4. SERVER AND AI CLIENT INITIALIZATION
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=config['server'].get('allowed_origins', ["*"]),
    allow_origin_regex=config['server'].get('allow_origin_regex'),
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# OpenAI Client (using gpt-4o-mini for high reasoning and low cost)
client = OpenAI(api_key=os.getenv("MODEL_API_KEY"))

class Query(BaseModel):
    question: str

@app.post("/ask")
async def answer_user(item: Query):
    try:
        # 1. RETRIEVAL: Refresh connection just in case the collector recreated it
        try:
            # We fetch the collection dynamically on every single request
            current_collection = chroma_client.get_collection(
                name="rag_context", 
                embedding_function=openai_ef
            )
        except Exception:
            # If it fails, it means the collector is deleting/rebuilding the DB in this exact second
            return {
                "response": "I am currently updating my knowledge base. Please ask me again in about 10 seconds.", 
                "status": "updating"
            }

        # We search inside the freshly retrieved collection
        results = current_collection.query(
            query_texts=[item.question],
            n_results=config['embeddings']['top_k']
        )
        retrieved_context = "\n---\n".join(results['documents'][0])
        
        # 2. CONSTRUCTION: Combine YAML prompt with actual retrieved data
        full_system_message = (
            f"{config['ai']['system_prompt']}\n\n"
            f"### RETRIEVED CONTEXT ###\n"
            f"{retrieved_context}"
        )

        # 3. GENERATION: Send the combined data to OpenAI
        response = client.chat.completions.create(
            model=config['ai']['model'],
            messages=[
                {"role": "system", "content": full_system_message},
                {"role": "user", "content": item.question}
            ],
            temperature=config['embeddings']['temperature']
        )
        
        return {
            "response": response.choices[0].message.content,
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Error processing question '{item.question}': {e}")
        return {"error": str(e)}

def get_server_bind(config):
    public_url = config['server'].get('public_url')
    if public_url:
        parsed = urlparse(public_url)
        if parsed.hostname:
            port = parsed.port
            if port is None:
                port = 443 if parsed.scheme == 'https' else 80
            return parsed.hostname, port
    return config['server']['host'], config['server']['port']

# 7. EXECUTION ENTRY POINT
if __name__ == "__main__":
    logger.info("Starting FastAPI server...")
    import uvicorn
    host, port = get_server_bind(config)
    uvicorn.run(
        app,
        host=host,
        port=port
    )