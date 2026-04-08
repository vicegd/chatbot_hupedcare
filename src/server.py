import os
import chromadb
from chromadb.utils import embedding_functions
from fastapi import FastAPI
from pydantic import BaseModel
from openai import OpenAI
from dotenv import load_dotenv
import utils.helper as helper

# 1. INITIAL SETUP
load_dotenv()
config = helper.config

# Disable local transformer warnings since we are using official API
os.environ['TRANSFORMERS_OFFLINE'] = '1'

# 2. EMBEDDING CONFIGURATION (Official OpenAI)
# This model ensures superior semantic search, connecting terms like 'ferry' and 'ship'
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.getenv("MODEL_API_KEY"),
    model_name=config['ai']['embedding_model']
)

# 3. CHROMADB CONNECTION
# Locate the persistent vector database folder defined in config
db_path = os.path.join(config['storage']['data_folder'], "vector_db")
chroma_client = chromadb.PersistentClient(path=db_path)

# Retrieve the collection (Make sure to rebuild it with the new vector_processor first)
collection = chroma_client.get_collection(
    name="rag_context", 
    embedding_function=openai_ef
)

# 4. SERVER AND AI CLIENT INITIALIZATION
app = FastAPI()

# OpenAI Client (using gpt-4o-mini for high reasoning and low cost)
client = OpenAI(api_key=os.getenv("MODEL_API_KEY"))

class Query(BaseModel):
    question: str

@app.post("/ask")
async def answer_user(item: Query):
    try:
        # 1. RETRIEVAL: Get chunks from ChromaDB
        results = collection.query(
            query_texts=[item.question],
            n_results=6
        )
        retrieved_context = "\n---\n".join(results['documents'][0])
        
        # 2. CONSTRUCTION: Combine YAML prompt with actual data
        # We use a clean f-string to separate identity from data
        full_system_message = (
            f"{config['ai']['system_prompt']}\n\n"
            f"### RETRIEVED CONTEXT ###\n"
            f"{retrieved_context}"
        )

        # 3. GENERATION: Send to OpenAI
        response = client.chat.completions.create(
            model=config['ai']['model'],
            messages=[
                {"role": "system", "content": full_system_message},
                {"role": "user", "content": item.question}
            ],
            temperature=0.2
        )
        
        return {
            "response": response.choices[0].message.content,
            "status": "success"
        }
        
    except Exception as e:
        return {"error": str(e)}

# 7. EXECUTION ENTRY POINT
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host=config['server']['host'], 
        port=config['server']['port']
    )