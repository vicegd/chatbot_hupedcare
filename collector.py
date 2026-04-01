import os
import yaml
import json
import base64
import mysql.connector
from ftplib import FTP
from bs4 import BeautifulSoup
from openai import OpenAI
from dotenv import load_dotenv
from datetime import datetime

# Load environment and configuration
load_dotenv()

def load_config():
    with open("config.yaml", "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

config = load_config()
client = OpenAI(base_url=config['ai']['base_url'], api_key=os.getenv("GROQ_API_KEY"))
METADATA_FILE = os.path.join(config['storage']['data_folder'], ".metadata.json")

# --- METADATA HELPERS ---
def load_metadata():
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_metadata(metadata):
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=4)

# --- FTP INCREMENTAL LOGIC ---
def sync_ftp_files(metadata):
    ftp_cfg = config['ftp']
    temp_folder = config['storage'].get('local_temp_folder', 'TEMP_DOWNLOADS')
    
    if not os.path.exists(temp_folder):
        os.makedirs(temp_folder)

    updated_files = []

    try:
        print(f"Connecting to FTP: {ftp_cfg['host']}...")
        ftp = FTP(ftp_cfg['host'])
        ftp.login(user=ftp_cfg['user'], passwd=ftp_cfg['password'])
        ftp.cwd(ftp_cfg['remote_path'])

        # Get list of files
        files = ftp.nlst()
        
        for filename in files:
            # We only care about HTML for this example
            if filename.endswith(".html"):
                # Get Remote Modification Time
                # MDTM command returns: '213 YYYYMMDDHHMMSS'
                response = ftp.sendcmd(f"MDTM {filename}")
                remote_mtime = response[4:] 
                
                # Check if file is new or modified
                if metadata.get(filename) != remote_mtime:
                    print(f"Update detected for {filename}. Downloading...")
                    local_path = os.path.join(temp_folder, filename)
                    
                    with open(local_path, "wb") as f:
                        ftp.retrbinary(f"RETR {filename}", f.write)
                    
                    metadata[filename] = remote_mtime
                    updated_files.append(local_path)
                else:
                    print(f"Skipping {filename} (Remote version matches local).")

        ftp.quit()
        return updated_files, metadata
    except Exception as e:
        print(f"FTP Error: {e}")
        return [], metadata

# --- HTML CONTENT EXTRACTION ---
def extract_html_text(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, 'html.parser')
            for tag in soup(["script", "style"]): tag.decompose()
            return soup.get_text(separator=' ', strip=True)
    except Exception as e:
        return f"Error reading {file_path}: {e}"

# --- MASTER COLLECTION FLOW ---
def run_master_collection():
    metadata = load_metadata()
    final_context = "SYSTEM CONTEXT AS OF " + datetime.now().strftime("%Y-%m-%d %H:%M") + "\n"
    
    # 1. Sync and Download only new/modified files via FTP
    new_local_files, updated_metadata = sync_ftp_files(metadata)
    
    # 2. Process existing files in TEMP_DOWNLOADS to build context
    # Note: In a production RAG system, you'd use a database (Vector DB) 
    # but for your low-spec PC, we read from the local temp folder.
    temp_folder = config['storage'].get('local_temp_folder', 'TEMP_DOWNLOADS')
    
    if os.path.exists(temp_folder):
        final_context += "\n=== REMOTE WEB CONTENT (SYNCED) ===\n"
        for filename in os.listdir(temp_folder):
            if filename.endswith(".html"):
                content = extract_html_text(os.path.join(temp_folder, filename))
                final_context += f"\nSOURCE: {filename}\n{content}\n"

    # 3. Save Context and Metadata
    output_path = os.path.join(config['storage']['data_folder'], "master_context.txt")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(final_context)
    
    save_metadata(updated_metadata)
    print(f"\nMaster context updated at: {output_path}")

if __name__ == "__main__":
    run_master_collection()