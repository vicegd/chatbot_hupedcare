import hashlib
import os

import utils.helper as helper
import utils.logger as logger
import utils.sql_collector as sql_collector

logger = logger.setup_logger(logger_name="data_collector", log_filename="collector.log")

def get_file_hash(filepath):
    """Return an MD5 hash for the file stored at the given path.

    Args:
        filepath: Absolute or relative path to the file whose contents should
            be hashed.

    Returns:
        The hexadecimal MD5 digest of the file contents.
    """
    hasher = hashlib.md5()
    with open(filepath, 'rb') as file_handle:
        file_bytes = file_handle.read()
        hasher.update(file_bytes)
    return hasher.hexdigest()

def run_collector():
    """Execute the end-to-end ingestion and indexing pipeline.

    The collector prepares local working folders, processes downloaded source
    files into cached text, appends SQL content, assembles the final
    `master_context.txt`, and refreshes the vector database only when the
    resulting context changed.
    """
    # Reuse the shared configuration and persisted metadata assembled by helper.py.
    config = helper.config
    metadata = helper.metadata

    temp_downloads_dir = os.path.join(config['storage']['data_folder'], "TEMP_DOWNLOADS")
    cache_text_dir = os.path.join(config['storage']['data_folder'], "CACHE_TEXT")
    logger.debug(f"Collector data directory: {config['storage']['data_folder']}")
    logger.debug(f"Temporary downloads directory: {temp_downloads_dir}")
    logger.debug(f"Cache text directory: {cache_text_dir}")
    
    # Ensure the working directories exist before starting the pipeline.
    if not os.path.exists(temp_downloads_dir): os.makedirs(temp_downloads_dir)
    if not os.path.exists(cache_text_dir): os.makedirs(cache_text_dir)

    # 1. SYNC FTP FILES
    logger.info("1. SYNCING FTP FILES...")
    # FTP sync can be enabled when remote mirroring is required.
    # import utils.ftp_collector as ftp_collector
    # updated_files, metadata = ftp_collector.sync_ftp_files(metadata, temp_downloads_dir)

    # 2. PURGE ORPHANED CACHE
    logger.info("2. PURGING ORPHANED CACHE FILES...")
    expected_cache_files = set()
    for root, _, files in os.walk(temp_downloads_dir):
        for file_name in files:
            # Cache filenames flatten the relative path so each source has a stable text mirror.
            relative_path = os.path.relpath(os.path.join(root, file_name), temp_downloads_dir)
            expected_cache_files.add(relative_path.replace(os.sep, "_") + ".txt")
    logger.debug(f"Expected cache file count: {len(expected_cache_files)}")

    for cache_file_name in os.listdir(cache_text_dir):
        if cache_file_name not in expected_cache_files:
            logger.info(f"Cleanup: Removing {cache_file_name} (no longer on server)")
            os.remove(os.path.join(cache_text_dir, cache_file_name))

    # 3. PROCESS FILES
    logger.info(f"3. PROCESSING UPDATES IN {temp_downloads_dir}...")
    for root, _, files in os.walk(temp_downloads_dir):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            relative_path = os.path.relpath(file_path, temp_downloads_dir)
            cache_file_path = os.path.join(cache_text_dir, relative_path.replace(os.sep, "_") + ".txt")
            
            if not os.path.exists(cache_file_path) or os.path.getmtime(file_path) > os.path.getmtime(cache_file_path):
                logger.info(f"  -> Processing: {relative_path}")
                normalized_path = file_path.lower()
                extracted_text = ""
                logger.debug(f"Detected source file for processing: {file_path}")
                
                try:
                    # Pick the extraction strategy based on the file extension.
                    if normalized_path.endswith(('.html', '.htm', '.php')):
                        extracted_text = helper.extract_from_html_or_php(file_path)
                    elif normalized_path.endswith(('.jpg', '.png', '.jpeg', '.webp')):
                        extracted_text = helper.extract_description_from_image_with_ai(file_path)
                    elif normalized_path.endswith(('.mp3', '.wav', '.m4a', '.flac')):
                        extracted_text = helper.extract_description_from_audio_with_ai(file_path)
                    elif normalized_path.endswith('.docx'):
                        extracted_text = helper.extract_from_docx(file_path)
                    elif normalized_path.endswith('.doc'):
                        extracted_text = helper.extract_from_doc(file_path)
                    elif normalized_path.endswith('.pdf'):
                        extracted_text = helper.extract_from_pdf(file_path)
                    elif normalized_path.endswith('.txt'):
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as file_handle:
                            extracted_text = helper.extract_clean_text(file_handle.read())
                    logger.debug(f"Extracted {len(extracted_text)} characters from {relative_path}")
               
                    # Persist the processed text even when the extractor returns an empty payload.
                    with open(cache_file_path, "w", encoding="utf-8") as file_handle:
                        file_handle.write(extracted_text if extracted_text.strip() else "No relevant content found.")
                except Exception as e:
                    logger.exception(f"Error processing {file_name}: {e}")

    # 4. ASSEMBLE MASTER CONTEXT
    logger.info("4. ASSEMBLING MASTER CONTEXT...")
    unique_lines = set()
    master_lines = ["SYSTEM CONTEXT - RAG KNOWLEDGE BASE\n"]
    
    # 5. ADD SQL DATA
    logger.info("5. ADDING SQL DATA...")
    sql_context = sql_collector.collect_sql_data(config)
    logger.debug(f"Collected {len(sql_context)} characters from SQL sources")
    master_lines.append(sql_context)

    # 6. ADD CACHED FILES WITH SOURCE HEADERS
    logger.info("6. ADDING CACHED FILES WITH SOURCE HEADERS...")
    for cache_file_name in os.listdir(cache_text_dir):
        source_label = cache_file_name.replace(".txt", "").replace("_", "/")
        source_added = False
        
        with open(os.path.join(cache_text_dir, cache_file_name), "r", encoding="utf-8") as file_handle:
            for line in file_handle:
                clean_line = line.strip()
                # De-duplicate at line level so repeated snippets do not waste embedding budget.
                if clean_line and clean_line not in unique_lines and "No relevant content found." not in clean_line:
                    if not source_added:
                        # Add a header once per file so the LLM can cite the origin.
                        master_lines.append(f"\n--- SOURCE: {source_label} ---")
                        source_added = True
                    
                    unique_lines.add(clean_line)
                    master_lines.append(clean_line)
        logger.debug(f"Processed cached source: {source_label}")

    # 7. SAVE EVERYTHING
    logger.info("7. SAVING MASTER CONTEXT...")
    output_path = os.path.join(config['storage']['data_folder'], "master_context.txt")
    with open(output_path, "w", encoding="utf-8") as file_handle:
        file_handle.write("\n".join(master_lines))
    helper.save_metadata(metadata)
    logger.debug(f"Master context line count: {len(master_lines)}")
    logger.info(f"Done! Context rebuilt at {output_path}")

    # 8. UPDATE VECTOR DATABASE
    logger.info("8. UPDATING VECTOR DATABASE (EMBEDDINGS)...")
    master_path = os.path.join(config['storage']['data_folder'], "master_context.txt")
    if os.path.exists(master_path):
        # 1. Get current hash and load metadata
        current_hash = get_file_hash(master_path)
        metadata = helper.load_metadata()
        logger.debug(f"Current master context hash: {current_hash}")
        
        # 2. Compare hashes
        if metadata.get("master_context_hash") == current_hash:
            logger.info("   -> [CACHE] No changes in master_context.txt.")
            logger.info("   -> [CACHE] Skipping OpenAI embeddings to save API costs.")
        else:
            logger.info("   -> [UPDATE] Changes detected! Sending data to OpenAI...")
            
            # 3. Call the worker to do the heavy lifting
            import utils.vector_processor as vector_processor
            vector_processor.update_vector_db()
            
            # 4. Save the new hash for next time
            # The stored hash avoids rebuilding embeddings when the assembled context is unchanged.
            metadata["master_context_hash"] = current_hash
            helper.save_metadata(metadata)
            logger.debug("Stored new master context hash in metadata")
            logger.info("   -> [SUCCESS] Vector database updated successfully.")
    else:
        logger.error("   -> [ERROR] master_context.txt not found!")

    logger.info("Done! Pipeline finished.")

if __name__ == "__main__":
    logger.info("Starting collector...")
    run_collector()