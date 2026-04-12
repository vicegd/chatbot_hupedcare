import os
import warnings

import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

import utils.helper as helper

warnings.filterwarnings("ignore", category=UserWarning)
import utils.logger as logger

logger = logger.setup_logger(logger_name="vector_processor", log_filename="vector_processor.log")

def update_vector_db():
    """Rebuild the ChromaDB collection from the current master context.

    The function reads the assembled context file, splits it into semantic
    chunks, recreates the `rag_context` collection, and uploads the new
    documents so retrieval stays aligned with the latest ingested data.
    """
    config = helper.config
    # 1. API configuration.
    logger.debug(f"Embedding model configured as {config['embeddings']['embedding_model']}")
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("MODEL_API_KEY"),
        model_name=config['embeddings']['embedding_model']
    )

    # 2. Read Master Context
    master_path = os.path.join(config['storage']['data_folder'], "master_context.txt")
    logger.debug(f"Loading master context from {master_path}")
    with open(master_path, "r", encoding="utf-8") as file_handle:
        full_text = file_handle.read()
    logger.debug(f"Master context size: {len(full_text)} characters")

    # 3. Chunking
    # Keep source headers as preferred separators so related fragments stay grouped when possible.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config['embeddings']['max_chunk_size'],
        chunk_overlap=config['embeddings']['chunk_overlap'],
        separators=["\n--- SOURCE: ", "\n[DB | ", "\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_text(full_text)
    logger.debug(f"Generated {len(chunks)} chunks for embedding")

    # 4. ChromaDB connection.
    db_path = os.path.join(config['storage']['data_folder'], "vector_db")
    logger.debug(f"Connecting to ChromaDB at {db_path}")
    chroma_client = chromadb.PersistentClient(path=db_path)
    
    if "rag_context" in [collection.name for collection in chroma_client.list_collections()]:
        logger.debug("Existing rag_context collection found and will be replaced")
        chroma_client.delete_collection(name="rag_context")
    
    # Rebuild the collection from scratch so the embedding store always mirrors the latest master context.
    collection = chroma_client.create_collection(name="rag_context", embedding_function=openai_ef)

    # 5. Insert chunks into the collection.
    collection.add(
        documents=chunks,
        ids=[f"id_{i}" for i in range(len(chunks))]
    )
    logger.info(f"Success: {len(chunks)} fragments indexed with OpenAI.")