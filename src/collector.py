import os, json
from datetime import datetime
import utils.collector_helper as helper
import utils.ftp_collector as ftp_c
import utils.sql_collector as sql_c

config = helper.config
metadata = helper.metadata

def run_master_collection():
    temp_folder = os.path.join(config['storage']['data_folder'], "TEMP_DOWNLOADS")
    cache_folder = os.path.join(config['storage']['data_folder'], "CACHE_TEXT")
    
    if not os.path.exists(temp_folder): os.makedirs(temp_folder)
    if not os.path.exists(cache_folder): os.makedirs(cache_folder)

    #1. SYNC FTP
    _, metadata = ftp_c.sync_ftp_files(metadata, config)

    #2. PURGE ORPHANED CACHE
    print("Purging orphaned cache files...")
    current_temp_files = set()
    for root, _, files in os.walk(temp_folder):
        for fname in files:
            rel_path = os.path.relpath(os.path.join(root, fname), temp_folder)
            current_temp_files.add(rel_path.replace(os.sep, "_") + ".txt")

    for c_file in os.listdir(cache_folder):
        if c_file not in current_temp_files:
            print(f"Cleanup: Removing {c_file} (no longer in server)")
            os.remove(os.path.join(cache_folder, c_file))

    #3. PROCESS FILES (Aquí estaba el 'pass')
    print(f"Processing updates in {temp_folder}...")
    for root, _, files in os.walk(temp_folder):
        for fname in files:
            f_path = os.path.join(root, fname)
            rel_path = os.path.relpath(f_path, temp_folder)
            c_path = os.path.join(cache_folder, rel_path.replace(os.sep, "_") + ".txt")
            
            if not os.path.exists(c_path) or os.path.getmtime(f_path) > os.path.getmtime(c_path):
                print(f"  -> Processing: {rel_path}")
                ext = f_path.lower()
                desc = ""
                
                try:
                    if ext.endswith(('.html', '.php')): 
                        desc = helper.extract_from_html_or_php(f_path)
                    elif ext.endswith(('.jpg', '.png', '.jpeg', '.webp')): 
                        desc = helper.describe_image_with_ai(f_path)
                    elif ext.endswith(('.mp4', '.webm', '.mov')): 
                        desc = helper.process_video_with_ai(f_path)
                    elif ext.endswith('.pdf'): 
                        desc = helper.extract_from_pdf(f_path)
                    elif ext.endswith('.txt'):
                        with open(f_path, 'r', encoding='utf-8', errors='ignore') as f:
                            desc = helper.clean_text(f.read())
               
                    with open(c_path, "w", encoding="utf-8") as f:
                        f.write(desc if desc.strip() else "No relevant content found.")
                except Exception as e:
                    print(f"Error processing {fname}: {e}")

    #4. ASSEMBLE AND DEDUPLICATE
    unique_lines = set()
    master_lines = [f"SYSTEM CONTEXT - UPDATED: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"]
    
    #5. Add MySQL Data
    #master_lines.append(sql_c.collect_mysql_data(config))

    #6. Add Cached Files with Source Headers
    for c_file in os.listdir(cache_folder):
        source_label = c_file.replace(".txt", "").replace("_", "/")
        source_added = False
        
        with open(os.path.join(cache_folder, c_file), "r", encoding="utf-8") as f:
            for line in f:
                clean = line.strip()
                # Filtros: no vacío, no repetido, no mensajes de error
                if clean and clean not in unique_lines and "No relevant content" not in clean:
                    if not source_added:
                        master_lines.append(f"\n--- SOURCE: {source_label} ---")
                        source_added = True
                    
                    unique_lines.add(clean)
                    master_lines.append(clean)

    #7. SAVE EVERYTHING
    output_path = os.path.join(config['storage']['data_folder'], "master_context.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(master_lines))
    
    with open(METADATA_FILE, "w") as f: 
        json.dump(metadata, f, indent=4)
        
    print(f"Done! Context rebuilt at {output_path}")

if __name__ == "__main__":
    run_master_collection()