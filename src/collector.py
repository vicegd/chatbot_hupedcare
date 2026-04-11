import os
import utils.helper as helper
import utils.ftp_collector as ftp_c
import utils.sql_collector as sql_c
import hashlib
import utils.logger as logger

logger = logger.setup_logger(logger_name="data_collector", log_filename="collector.log")

def get_file_hash(filepath):
    """Generates an MD5 hash of a file to detect if its content has changed."""
    hasher = hashlib.md5()
    with open(filepath, 'rb') as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()

def run_collector():
    config = helper.config
    metadata = helper.metadata

    temp_folder = os.path.join(config['storage']['data_folder'], "TEMP_DOWNLOADS")
    cache_folder = os.path.join(config['storage']['data_folder'], "CACHE_TEXT")
    
    if not os.path.exists(temp_folder): os.makedirs(temp_folder)
    if not os.path.exists(cache_folder): os.makedirs(cache_folder)

    #1. SYNC FTP FILES
    logger.info("1. SYNCING FTP FILES...")
    #updated_files, metadata = ftp_c.sync_ftp_files(metadata, temp_folder)

    #2. PURGE ORPHANED CACHE
    logger.info("2. PURGING ORPHANED CACHE FILES...")
    current_temp_files = set()
    for root, _, files in os.walk(temp_folder):
        for fname in files:
            rel_path = os.path.relpath(os.path.join(root, fname), temp_folder)
            current_temp_files.add(rel_path.replace(os.sep, "_") + ".txt")

    for c_file in os.listdir(cache_folder):
        if c_file not in current_temp_files:
            logger.info(f"Cleanup: Removing {c_file} (no longer in server)")
            os.remove(os.path.join(cache_folder, c_file))

    #3. PROCESS FILES
    logger.info(f"3. PROCESSING UPDATES IN {temp_folder}...")
    for root, _, files in os.walk(temp_folder):
        for fname in files:
            f_path = os.path.join(root, fname)
            rel_path = os.path.relpath(f_path, temp_folder)
            c_path = os.path.join(cache_folder, rel_path.replace(os.sep, "_") + ".txt")
            
            if not os.path.exists(c_path) or os.path.getmtime(f_path) > os.path.getmtime(c_path):
                logger.info(f"  -> Processing: {rel_path}")
                ext = f_path.lower()
                desc = ""
                
                try:
                    if ext.endswith(('.html', '.htm', '.php')): 
                        desc = helper.extract_from_html_or_php(f_path)
                    elif ext.endswith(('.jpg', '.png', '.jpeg', '.webp')): 
                        desc = helper.extract_description_from_image_with_ai(f_path)
                    elif ext.endswith(('.mp3', '.wav', '.m4a', '.flac')):
                        desc = helper.extract_description_from_audio_with_ai(f_path)
                    elif ext.endswith('.docx'):
                        desc = helper.extract_from_docx(f_path)
                    elif ext.endswith('.doc'):
                     desc = helper.extract_from_doc(f_path)
                    elif ext.endswith('.pdf'): 
                          desc = helper.extract_from_pdf(f_path)
                    elif ext.endswith('.txt'):
                          with open(f_path, 'r', encoding='utf-8', errors='ignore') as f:
                             desc = helper.extract_clean_text(f.read())
               
                    with open(c_path, "w", encoding="utf-8") as f:
                        f.write(desc if desc.strip() else "No relevant content found.")
                except Exception as e:
                    print(f"Error processing {fname}: {e}")

    #4. ASSEMBLE MASTER CONTEXT
    logger.info("4. ASSEMBLING MASTER CONTEXT...")
    unique_lines = set()
    master_lines = ["SYSTEM CONTEXT - RAG KNOWLEDGE BASE\n"]
    
    #5. ADD SQL DATA
    logger.info("5. ADDING SQL DATA...")
    master_lines.append(sql_c.collect_sql_data(config))

    #6. ADD CACHED FILES WITH SOURCE HEADERS
    logger.info("6. ADDING CACHED FILES WITH SOURCE HEADERS...")
    for c_file in os.listdir(cache_folder):
        source_label = c_file.replace(".txt", "").replace("_", "/")
        source_added = False
        
        with open(os.path.join(cache_folder, c_file), "r", encoding="utf-8") as f:
            for line in f:
                clean = line.strip()
                if clean and clean not in unique_lines and "No relevant content found." not in clean:
                    if not source_added:
                        master_lines.append(f"\n--- SOURCE: {source_label} ---")
                        source_added = True
                    
                    unique_lines.add(clean)
                    master_lines.append(clean)

    #7. SAVE EVERYTHING
    logger.info("7. SAVING MASTER CONTEXT...")
    output_path = os.path.join(config['storage']['data_folder'], "master_context.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(master_lines))
    helper.save_metadata(metadata)
    logger.info(f"Done! Context rebuilt at {output_path}")

    #8. UPDATE VECTOR DATABASE
    logger.info("8. UPDATING VECTOR DATABASE (EMBEDDINGS)...")
    master_path = os.path.join(config['storage']['data_folder'], "master_context.txt")
    if os.path.exists(master_path):
        # 1. Get current hash and load metadata
        current_hash = get_file_hash(master_path)
        metadata = helper.load_metadata()
        
        # 2. Compare hashes
        if metadata.get("master_context_hash") == current_hash:
            logger.info("   -> [CACHE] No changes in master_context.txt.")
            logger.info("   -> [CACHE] Skipping OpenAI embeddings to save API costs.")
        else:
            logger.info("   -> [UPDATE] Changes detected! Sending data to OpenAI...")
            
            # 3. Call the worker to do the heavy lifting
            import utils.vector_processor as vector_p
            vector_p.update_vector_db()
            
            # 4. Save the new hash for next time
            metadata["master_context_hash"] = current_hash
            helper.save_metadata(metadata)
            logger.info("   -> [SUCCESS] Vector database updated successfully.")
    else:
        logger.error("   -> [ERROR] master_context.txt not found!")

    logger.info("Done! Pipeline finished.")

if __name__ == "__main__":
    logger.info("Starting collector...")
    run_collector()