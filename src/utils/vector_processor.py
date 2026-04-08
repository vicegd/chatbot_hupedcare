import os
import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter
import utils.helper as helper
import warnings
warnings.filterwarnings("ignore", category=UserWarning)

def update_vector_db():
    config = helper.config
    # 1. API Configuration (OpenAI Oficial)
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("MODEL_API_KEY"),
        model_name=config['embeddings']['embedding_model']
    )

    # 2. Read Master Context
    master_path = os.path.join(config['storage']['data_folder'], "master_context.txt")
    with open(master_path, "r", encoding="utf-8") as f:
        full_text = f.read()

    # 3. Chunking
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config['embeddings']['max_chunk_size'],
        chunk_overlap=config['embeddings']['chunk_overlap'],
        separators=["\n--- SOURCE: ", "\n[DB | ", "\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_text(full_text)

    # 4. ChromaDB Connection
    db_path = os.path.join(config['storage']['data_folder'], "vector_db")
    client = chromadb.PersistentClient(path=db_path)
    
    if "rag_context" in [c.name for c in client.list_collections()]:
        client.delete_collection(name="rag_context")
    
    collection = client.create_collection(name="rag_context", embedding_function=openai_ef)

    # 5. Insert
    collection.add(
        documents=chunks,
        ids=[f"id_{i}" for i in range(len(chunks))]
    )
    print(f"Success: {len(chunks)} fragments indexed with OpenAI.")