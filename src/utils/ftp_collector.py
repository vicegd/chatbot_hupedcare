import os
from ftplib import FTP

def sync_ftp_files(metadata, temp_folder):
    """
    Synchronizes local TEMP_DOWNLOADS with the remote FTP server.
    Returns a list of updated files and the modified metadata.
    """
    updated_files = []
    remote_files_found = set()
    
    #Extensions we care about for the RAG system
    VALID_EXTENSIONS = (
        ".html", ".htm", ".php", ".txt", ".pdf", ".docx", 
        ".doc",".jpg", ".jpeg", ".png", ".webp", ".mp4", 
        ".webm", ".mov", ".mp3", ".wav", ".m4a", ".flac"
    )

    try:
        host = os.getenv("FTP_HOST")
        print(f"Connecting to FTP: {host}")
        
        ftp = FTP(host)
        ftp.login(user=os.getenv("FTP_USER"), passwd=os.getenv("FTP_PASSWORD"))
        
        remote_root = os.getenv("FTP_REMOTE_PATH", "/")
        ftp.cwd(remote_root)

        def walk_recursive(remote_path, local_path):
            """Internal helper to navigate FTP folders and download files."""
            if not os.path.exists(local_path):
                os.makedirs(local_path)

            try:
                #mlsd is more reliable for metadata than nlstd
                for name, facts in ftp.mlsd(path=remote_path):
                    if name in (".", ".."): 
                        continue

                    remote_full_path = os.path.join(remote_path, name).replace("\\", "/")
                    local_full_path = os.path.join(local_path, name)

                    if facts['type'] == 'dir':
                        #It's a folder, go deeper
                        walk_recursive(remote_full_path, local_full_path)
                    
                    elif facts['type'] == 'file':
                        if name.lower().endswith(VALID_EXTENSIONS):
                            remote_files_found.add(remote_full_path)

                            #Check modification time from server
                            #MDTM is standard for getting file last-modified date
                            response = ftp.sendcmd(f"MDTM {remote_full_path}")
                            remote_mtime = response[4:]

                            #Sync logic: Only download if it's new or timestamp changed
                            if metadata.get(remote_full_path) != remote_mtime:
                                print(f"Update: {remote_full_path} -> Downloading...")
                                
                                with open(local_full_path, "wb") as f:
                                    ftp.retrbinary(f"RETR {remote_full_path}", f.write)
                                
                                metadata[remote_full_path] = remote_mtime
                                updated_files.append(local_full_path)

            except Exception as e:
                print(f"Error while walking {remote_path}: {e}")

        # Start the recursive sync
        walk_recursive(remote_root, temp_folder)

        #PURGE local files that no longer exist on the server and clean metadata
        stored_paths = list(metadata.keys())
        for path_in_meta in stored_paths:
            if path_in_meta not in remote_files_found:
                print(f"Was first deleted on server: {path_in_meta} -> Cleaning local copy...")
                
                rel_path = os.path.relpath(path_in_meta, remote_root)
                local_to_delete = os.path.join(temp_folder, rel_path)
                
                if os.path.exists(local_to_delete):
                    try:
                        os.remove(local_to_delete)
                    except Exception as e:
                        print(f"Error deleting {local_to_delete}: {e}")

                del metadata[path_in_meta]

        ftp.quit()
        print("FTP Sync completed successfully.")
        return updated_files, metadata

    except Exception as e:
        print(f"FTP Fatal Error: {e}")
        return [], metadata