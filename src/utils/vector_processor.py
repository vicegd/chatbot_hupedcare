"""
=============================================================================
RAG VECTOR PROCESSOR
=============================================================================

This module acts as the "Mathematical Librarian" of the RAG system. 

Language Models (LLMs) cannot read a 10,000-page document every time you ask 
them a question; it would be too slow and expensive. Instead, we use a Vector 
Database. This script takes the massive `master_context.txt` file, chops it 
 up into small, digestible paragraphs (Chunks), and converts them into numbers 
(Embeddings) so the Chatbot can perform instant semantic searches later.

How the pipeline works (Step-by-Step):
-----------------------------------------------------------------------------
1. LOAD ENGINE: Connects to the Embedding Model (e.g., OpenAI or Open Source).
2. READ CONTEXT: Loads the giant text file created by the `data_collector`.
3. SEMANTIC CHUNKING: It splits the giant file into smaller pieces (e.g., 1000 
   characters each). It uses smart separators to ensure it doesn't accidentally 
   cut a sentence in half or mix two different documents together.
4. MEMORY WIPE: It connects to the local ChromaDB database and deletes the old 
   knowledge base. This prevents duplicates and ensures the AI only remembers 
   the absolute latest version of the files.
5. VECTORIZATION: It sends the chunks to the Embedding model, turns them into 
   mathematical coordinates (vectors), and saves them into the database in batches
   to avoid exceeding API token limits.
=============================================================================
"""

import os
import time
import warnings

import chromadb
from chromadb.utils import embedding_functions
from langchain_text_splitters import RecursiveCharacterTextSplitter

import utils.helper as helper

# Suppress verbose warnings from third-party libraries (like Langchain or Chroma) 
# to keep our terminal output clean and professional.
warnings.filterwarnings("ignore", category=UserWarning)
import utils.logger as logger

# Initialize the logger specifically for the vector processing events
logger = logger.setup_logger(logger_name="vector_processor", log_filename="vector_processor.log")

def update_vector_db():
    """
    Rebuild the ChromaDB collection from the current master context.

    The function reads the assembled context file, splits it into semantic
    chunks, recreates the `rag_context` collection, and uploads the new
    documents in batches so retrieval stays aligned with the latest ingested data.
    """
    config = helper.config
    
    # ---------------------------------------------------------
    # 1. EMBEDDING API CONFIGURATION
    # ---------------------------------------------------------
    logger.debug(f"Embedding model configured as {config['embeddings']['embedding_model']}")
    
    # Initialize the engine that will convert words into numbers (Embeddings).
    # If you switched to an Open Source provider in config.yaml, this will securely
    # route the request using your environment API key.
    openai_ef = embedding_functions.OpenAIEmbeddingFunction(
        api_key=os.getenv("MODEL_API_KEY"),
        model_name=config['embeddings']['embedding_model']
    )

    # ---------------------------------------------------------
    # 2. READ THE ASSEMBLED MASTER CONTEXT
    # ---------------------------------------------------------
    master_path = os.path.join(config['storage']['data_folder'], "master_context.txt")
    logger.debug(f"Loading master context from {master_path}")
    
    with open(master_path, "r", encoding="utf-8") as file_handle:
        full_text = file_handle.read()
    logger.debug(f"Master context size: {len(full_text)} characters")

    # ---------------------------------------------------------
    # 3. SEMANTIC CHUNKING
    # ---------------------------------------------------------
    # We cannot feed the whole text to the database at once. We must chunk it.
    # The 'RecursiveCharacterTextSplitter' tries to split the text using the 
    # separators in order. 
    # 
    # Advanced feature: By prioritizing "\n--- SOURCE: " and "\n[DB | ", we 
    # force the system to keep data from the same file or database record 
    # grouped together as much as possible before splitting by paragraphs or lines.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=config['embeddings']['max_chunk_size'], # E.g., 1100 characters per chunk
        chunk_overlap=config['embeddings']['chunk_overlap'], # E.g., 200 characters of overlap to keep context flow
        separators=["\n--- SOURCE: ", "\n[DB | ", "\n\n", "\n", " ", ""]
    )
    
    # Execute the split
    chunks = text_splitter.split_text(full_text)
    total_chunks = len(chunks)
    logger.debug(f"Generated {total_chunks} chunks for embedding")

    # ---------------------------------------------------------
    # 4. CHROMADB DATABASE RESET
    # ---------------------------------------------------------
    db_path = os.path.join(config['storage']['data_folder'], "vector_db")
    logger.debug(f"Connecting to ChromaDB at {db_path}")
    
    # Connect to the local folder where the vector database is stored
    chroma_client = chromadb.PersistentClient(path=db_path)
    
    # Check if the "rag_context" collection already exists.
    # If it does, we DELETE it completely. 
    # Why: We do a "Full Rebuild" instead of an "Incremental Update" here because 
    # it guarantees there are no orphaned chunks or duplicate paragraphs in the AI's memory.
    if "rag_context" in [collection.name for collection in chroma_client.list_collections()]:
        logger.debug("Existing rag_context collection found and will be replaced")
        chroma_client.delete_collection(name="rag_context")
    
    # Create a fresh, empty collection and bind the Embedding Function to it
    collection = chroma_client.create_collection(
        name="rag_context", 
        embedding_function=openai_ef
    )

    # ---------------------------------------------------------
    # 5. BATCH VECTORIZATION AND STORAGE
    # ---------------------------------------------------------
    # We process chunks in batches to avoid OpenAI's "max_tokens_per_request" limits.
    BATCH_SIZE = 150  # Safe number of chunks per HTTP request
    
    logger.info(f"Starting vectorization in batches of {BATCH_SIZE}...")
    
    for i in range(0, total_chunks, BATCH_SIZE):
        batch_chunks = chunks[i : i + BATCH_SIZE]
        batch_ids = [f"id_{j}" for j in range(i, i + len(batch_chunks))]
        
        try:
            collection.add(
                documents=batch_chunks,
                ids=batch_ids
            )
            # CAMBIADO a .info y mejorado el texto para ver el progreso real
            logger.info(f"   -> Insertados {min(i + BATCH_SIZE, total_chunks)} de {total_chunks} fragmentos en la BD...")
            
            # Small pause to respect API rate limits (RPM - Requests Per Minute)
            time.sleep(0.5)
            
        except Exception as e:
            logger.error(f"Error vectorizing batch starting at chunk {i}: {e}")
            raise  # Re-raise the exception to stop the pipeline if embedding fails
            
    logger.info(f"Success: {total_chunks} fragments indexed and saved to Vector Database.")

    