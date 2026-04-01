import os, json
from datetime import datetime
from dotenv import load_dotenv
import collector_helper as helper
import ftp_collector as ftp_c
import mysql_collector as sql_c

load_dotenv()
config = helper.config
METADATA_FILE = os.path.join(config['storage']['data_folder'], ".metadata.json")

def load_metadata():
    return json.load(open(METADATA_FILE)) if os.path.exists(METADATA_FILE) else {}

def run_master_collection():
    metadata = load_metadata()
    temp_folder = os.path.join(config['storage']['data_folder'], "TEMP_DOWNLOADS")
    cache_folder = os.path.join(config['storage']['data_folder'], "CACHE_TEXT")
    if not os.path.exists(cache_folder): os.makedirs(cache_folder)

    # 1. Sync FTP
    _, metadata = ftp_c.sync_ftp_files(metadata, config)

    # 2. Process Files to Cache
    for root, _, files in os.walk(temp_folder):
        for fname in files:
            f_path = os.path.join(root, fname)
            rel_path = os.path.relpath(f_path, temp_folder)
            c_path = os.path.join(cache_folder, rel_path.replace(os.sep, "_") + ".txt")
            
            if not os.path.exists(c_path) or os.path.getmtime(f_path) > os.path.getmtime(c_path):
                ext = f_path.lower()
                desc = ""
                if ext.endswith(('.html', '.php')): desc = helper.extract_from_html_or_php(f_path)
                elif ext.endswith(('.jpg', '.png', '.webp')): desc = helper.describe_image_with_ai(f_path)
                elif ext.endswith(('.mp4', '.mov')): desc = helper.process_video_with_ai(f_path)
                elif ext.endswith('.pdf'): desc = helper.extract_from_pdf(f_path)
                
                with open(c_path, "w", encoding="utf-8") as f:
                    f.write(desc if desc.strip() else "No relevant content found.")

    # 3. Assemble and Deduplicate
    unique_lines = set()
    master_lines = [f"CONTEXT UPDATED: {datetime.now()}\n"]
    
    # Add MySQL Data
    master_lines.append(sql_c.collect_mysql_data(config))

    # Add Cached Files
    for c_file in os.listdir(cache_folder):
        with open(os.path.join(cache_folder, c_file), "r", encoding="utf-8") as f:
            for line in f:
                clean = line.strip()
                if clean and clean not in unique_lines and "No relevant content" not in clean:
                    unique_lines.add(clean)
                    master_lines.append(clean)

    with open(os.path.join(config['storage']['data_folder'], "master_context.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(master_lines))
    
    with open(METADATA_FILE, "w") as f: json.dump(metadata, f)
    print("Master Collection Complete.")

if __name__ == "__main__":
    run_master_collection()