"""
=============================================================================
RAG DATA INGESTION PIPELINE
=============================================================================

This script acts as the core data collection engine for the Retrieval-Augmented 
Generation (RAG) system. Its primary job is to gather raw information from 
various sources, clean it, merge it, and prepare it for the Vector Database.

How the pipeline works (Step-by-Step):
-----------------------------------------------------------------------------
1. PREPARATION: It sets up temporary folders for raw downloads and cached text.
2. CLEANUP: It removes cached text for files that have been deleted from the server.
3. SMART EXTRACTION: It iterates through all raw files. Based on the file type:
   - Text/HTML/PDFs are parsed.
   - Images (.jpg, .png) are passed to an AI Vision model for description.
   - Audio files (.mp3, .wav) are transcribed using Whisper.
   * Optimization: It only processes files that are new or recently modified.
4. SQL INGESTION: It pulls structured relational data directly from the database.
5. CONTEXT ASSEMBLY: It merges the SQL data and the extracted file text into 
   a single `master_context.txt` file. It deduplicates lines and adds source 
   headers (e.g., "--- SOURCE: file.pdf ---") so the LLM can cite its sources.
6. VECTORIZATION (EMBEDDINGS): It calculates an MD5 hash of the master file. 
   If the hash hasn't changed since the last run, it skips the expensive 
   embedding process. If it has changed, it triggers the Vector Database update.
=============================================================================
"""

import hashlib
import os

from core.events import EventBus
from core.extraction_strategies import build_default_registry
import utils.helper as helper
import utils.logger as logger
import utils.sql_collector as sql_collector

# Initialize the logger for this specific module
logger = logger.setup_logger(logger_name="data_collector", log_filename="collector.log")


class LoggerObserver:
    """Observer that writes high-level ETL events to the application logger."""

    def __init__(self, log):
        self._log = log

    def on_event(self, event):
        details = " ".join(f"{key}={value}" for key, value in event.payload.items())
        if details:
            self._log.info(f"[EVENT] {event.name} {details}")
        else:
            self._log.info(f"[EVENT] {event.name}")

def get_file_hash(filepath):
    """
    Calculates the MD5 hash (a unique digital fingerprint) of a file.
    
    Why we do this:
    Updating the Vector Database (ChromaDB) via an Embedding API costs money 
    and processing time. By comparing the hash of the new master_context.txt 
    with the hash from the previous run, we can skip the embedding process 
    entirely if no files or database records have actually changed.
    """
    hasher = hashlib.md5()
    with open(filepath, 'rb') as file_handle:
        file_bytes = file_handle.read()
        hasher.update(file_bytes)
    return hasher.hexdigest()

def run_collector():
    """
    Executes the complete end-to-end data ingestion pipeline.
    """
    # Load configuration and metadata states globally managed by helper.py
    config = helper.config
    metadata = helper.metadata
    strategy_registry = build_default_registry()
    events = EventBus()
    events.subscribe(LoggerObserver(logger))

    # Define directories for raw downloaded files and their extracted text versions (cache)
    temp_downloads_dir = os.path.join(config['storage']['data_folder'], "TEMP_DOWNLOADS")
    cache_text_dir = os.path.join(config['storage']['data_folder'], "CACHE_TEXT")
    
    # Ensure the working directories exist before starting the pipeline
    if not os.path.exists(temp_downloads_dir): os.makedirs(temp_downloads_dir)
    if not os.path.exists(cache_text_dir): os.makedirs(cache_text_dir)

    # ---------------------------------------------------------
    # 1. SYNC FTP FILES FROM REMOTE SERVER
    # ---------------------------------------------------------
    logger.info("1. SYNCING FTP FILES...")
    # This module would download raw files from a remote server to 'temp_downloads_dir'
    import utils.ftp_collector as ftp_collector
    updated_files, metadata = ftp_collector.sync_ftp_files(metadata, temp_downloads_dir)
    events.publish("ftp_sync_completed", updated_files=len(updated_files))

    # ---------------------------------------------------------
    # 2. PURGE ORPHANED CACHE FILES
    # ---------------------------------------------------------
    logger.info("2. PURGING ORPHANED CACHE FILES...")
    # Build a list of what files SHOULD be in the cache based on currently downloaded files
    expected_cache_files = set()
    for root, _, files in os.walk(temp_downloads_dir):
        for file_name in files:
            # Flatten the path to create a stable text mirror filename
            relative_path = os.path.relpath(os.path.join(root, file_name), temp_downloads_dir)
            expected_cache_files.add(relative_path.replace(os.sep, "_") + ".txt")

    # If a text file exists in the cache but its original raw file is gone, delete the cache
    for cache_file_name in os.listdir(cache_text_dir):
        if cache_file_name not in expected_cache_files:
            logger.info(f"Cleanup: Removing {cache_file_name} (no longer on server)")
            os.remove(os.path.join(cache_text_dir, cache_file_name))
            events.publish("orphan_cache_purged", cache_file=cache_file_name)

    # ---------------------------------------------------------
    # 3. PROCESS NEW OR MODIFIED FILES
    # ---------------------------------------------------------
    logger.info(f"3. PROCESSING UPDATES IN {temp_downloads_dir}...")
    for root, _, files in os.walk(temp_downloads_dir):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            relative_path = os.path.relpath(file_path, temp_downloads_dir)
            cache_file_path = os.path.join(cache_text_dir, relative_path.replace(os.sep, "_") + ".txt")
            
            # SMART CACHE LOGIC: 
            # Only process if the cache doesn't exist, OR if the raw file was modified 
            # more recently than our cached text file.
            if not os.path.exists(cache_file_path) or os.path.getmtime(file_path) > os.path.getmtime(cache_file_path):
                logger.info(f"  -> Processing: {relative_path}")
                extracted_text = ""
                
                try:
                    # Strategy-based extraction keeps modality logic open for extension.
                    strategy = strategy_registry.resolve(file_path)
                    if strategy is None:
                        logger.debug(f"Skipping unsupported file type: {relative_path}")
                        events.publish("unsupported_file_skipped", file=relative_path)
                        continue

                    extracted_text = strategy.extract(file_path)
                    events.publish("file_extracted", file=relative_path)
               
                    # Save the extracted plain text to the cache directory
                    with open(cache_file_path, "w", encoding="utf-8") as file_handle:
                        file_handle.write(extracted_text if extracted_text.strip() else "No relevant content found.")
                except Exception as e:
                    logger.exception(f"Error processing {file_name}: {e}")
                    events.publish("file_extraction_failed", file=relative_path, error=str(e))

    # ---------------------------------------------------------
    # 4 & 5. ASSEMBLE MASTER CONTEXT & ADD SQL DATA
    # ---------------------------------------------------------
    logger.info("4. ASSEMBLING MASTER CONTEXT...")
    unique_lines = set() # Set to prevent duplicate lines and save embedding budget
    master_lines = ["SYSTEM CONTEXT - RAG KNOWLEDGE BASE\n"]
    
    logger.info("5. ADDING SQL DATA...")
    # Fetch structured data directly from the relational database
    sql_context = sql_collector.collect_sql_data(config)
    master_lines.append(sql_context)
    events.publish("sql_context_collected")

    # ---------------------------------------------------------
    # 6. ADD CACHED FILES WITH SOURCE CITATION HEADERS
    # ---------------------------------------------------------
    logger.info("6. ADDING CACHED FILES WITH SOURCE HEADERS...")
    for cache_file_name in os.listdir(cache_text_dir):
        # Reconstruct the original filename to use as a citation label
        source_label = cache_file_name.replace(".txt", "").replace("_", "/")
        source_added = False
        
        with open(os.path.join(cache_text_dir, cache_file_name), "r", encoding="utf-8") as file_handle:
            for line in file_handle:
                clean_line = line.strip()
                # De-duplicate: Ensure we don't send identical sentences multiple times
                if clean_line and clean_line not in unique_lines and "No relevant content found." not in clean_line:
                    if not source_added:
                        # Append the filename header before the text starts so the LLM can cite it
                        master_lines.append(f"\n--- SOURCE: {source_label} ---")
                        source_added = True
                    
                    unique_lines.add(clean_line)
                    master_lines.append(clean_line)

    # ---------------------------------------------------------
    # 7. SAVE THE ASSEMBLED CONTEXT
    # ---------------------------------------------------------
    logger.info("7. SAVING MASTER CONTEXT...")
    # Output the final, massive text file containing ALL collected knowledge
    output_path = os.path.join(config['storage']['data_folder'], "master_context.txt")
    with open(output_path, "w", encoding="utf-8") as file_handle:
        file_handle.write("\n".join(master_lines))
    events.publish("master_context_written", path=output_path)
    
    # Save the updated metadata state (managed by helper)
    helper.save_metadata(metadata)

    # ---------------------------------------------------------
    # 8. COST-SAVING VECTOR DATABASE UPDATE
    # ---------------------------------------------------------
    logger.info("8. UPDATING VECTOR DATABASE (EMBEDDINGS)...")
    if os.path.exists(output_path):
        # Hash the newly created master text file
        current_hash = get_file_hash(output_path)
        metadata = helper.load_metadata()
        
        # Compare against the hash from the previous execution
        if metadata.get("master_context_hash") == current_hash:
            logger.info("   -> [CACHE] No changes in master_context.txt.")
            logger.info("   -> [CACHE] Skipping Embedding API to save costs.")
            events.publish("vector_update_skipped")
        else:
            # Only if the file has changed, we run the expensive embedding process
            logger.info("   -> [UPDATE] Changes detected! Sending data to Embedding Model...")
            import utils.vector_processor as vector_processor
            
            # This converts text chunks into mathematical vectors in ChromaDB
            vector_processor.update_vector_db() 
            
            # Save the new hash so we don't process it again next time
            metadata["master_context_hash"] = current_hash
            helper.save_metadata(metadata)
            logger.info("   -> [SUCCESS] Vector database updated successfully.")
            events.publish("vector_update_completed")
    else:
        logger.error("   -> [ERROR] master_context.txt not found!")
        events.publish("master_context_missing")

if __name__ == "__main__":
    logger.info("Starting collector...")
    run_collector()