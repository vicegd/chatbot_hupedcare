"""
=============================================================================
RAG FTP SYNCHRONIZER
=============================================================================

This module acts as the "Bridge" between your company's live file server 
(FTP) and the local AI Knowledge Base. 

Instead of requiring humans to manually upload new PDFs or Word documents 
to the chatbot, this script automatically mirrors a remote FTP server.

How the pipeline works (Step-by-Step):
-----------------------------------------------------------------------------
1. CONNECTION: It securely connects to the remote FTP server using credentials 
   stored in the .env file.
2. FILTERING: It only looks for specific file types (PDF, DOCX, JPG, MP3, etc.) 
   that the `helper.py` knows how to extract text from. It ignores junk files.
3. SMART SYNC (Bandwidth Saver): It doesn't download everything every time. 
   It asks the FTP server for the "Last Modified" date of each file and compares 
   it against its internal memory (`metadata`). It ONLY downloads files that 
   are brand new or have been recently modified.
4. GHOST PURGE: If a human deletes a document from the remote FTP server, this 
   script detects the absence and deletes the local physical copy. This guarantees 
   the AI will not provide answers based on outdated or deleted policies.
=============================================================================
"""

import os
from ftplib import FTP

import utils.logger as logger

# Initialize the logger specifically for the FTP synchronization process
logger = logger.setup_logger(logger_name="ftp_collector", log_filename="ftp_collector.log")

def sync_ftp_files(metadata, temp_folder):
    """
    Synchronize the local temporary mirror with the remote FTP tree.

    Args:
        metadata: Dictionary that tracks the latest known remote modification
            timestamp for each synchronized file. (Acts as the system's memory).
        temp_folder: Local folder where remote files are downloaded and mirrored.

    Returns:
        A tuple `(updated_files, metadata)` where `updated_files` contains the
        local file paths downloaded during the current run and `metadata`
        contains the refreshed timestamp mapping.
    """
    updated_files = []
    
    # We use a Set to keep track of every file we see on the server today.
    # Later, we compare this against our memory and local drive to see if anything was deleted.
    remote_files_found = set()
    
    # Only mirror the file types that have downstream extractors in the helper.py.
    # Why: This prevents downloading heavy .exe, .zip, or unreadable proprietary files.
    VALID_EXTENSIONS = (
        ".html", ".htm", ".php", ".txt", ".pdf", ".docx", 
        ".doc",".jpg", ".jpeg", ".png", ".mp3", ".wav", ".m4a", ".flac"
    )

    try:
        # 1. Establish the FTP Connection
        host = os.getenv("FTP_HOST")
        logger.info(f"Connecting to FTP: {host}")
        logger.debug(f"FTP sync target folder: {temp_folder}")
        
        ftp = FTP(host)
        ftp.login(user=os.getenv("FTP_USER"), passwd=os.getenv("FTP_PASSWORD"))
        
        remote_root = os.getenv("FTP_REMOTE_PATH", "/")
        ftp.cwd(remote_root)
        logger.debug(f"FTP remote root set to {remote_root}")

        def walk_recursive(remote_path, local_path):
            """
            Internal helper function to navigate FTP folders folder-by-folder.
            It mirrors the exact remote folder structure on your local drive.
            """
            # Create the local directory if it doesn't exist yet
            if not os.path.exists(local_path):
                os.makedirs(local_path)

            try:
                # MLSD is a modern FTP command that lists directory contents 
                # AND provides metadata (like timestamps and types) in one fast request.
                for name, facts in ftp.mlsd(path=remote_path):
                    # Skip standard current/parent directory pointers
                    if name in (".", ".."): 
                        continue

                    remote_full_path = os.path.join(remote_path, name).replace("\\", "/")
                    local_full_path = os.path.join(local_path, name)

                    # If it's a folder, dive inside it (Recursive call)
                    if facts['type'] == 'dir':
                        logger.debug(f"Descending into FTP directory: {remote_full_path}")
                        walk_recursive(remote_full_path, local_full_path)
                    
                    # If it's a file, check if we need to download it
                    elif facts['type'] == 'file':
                        # Check against our whitelist of readable extensions
                        if name.lower().endswith(VALID_EXTENSIONS):
                            remote_files_found.add(remote_full_path)
                            logger.debug(f"Eligible remote file found: {remote_full_path}")

                            # MLSD exposes the server modification timestamp in the 'modify' field.
                            remote_mtime = facts.get('modify')

                            # Fallback strategy: Some older legacy FTP servers don't support MLSD.
                            # If 'modify' is empty, we explicitly ask for the time using MDTM.
                            if not remote_mtime:
                                response = ftp.sendcmd(f"MDTM {remote_full_path}")
                                remote_mtime = response[4:]

                            # SMART SYNC LOGIC:
                            # Compare the file's current timestamp with our saved metadata.
                            # Download ONLY if the timestamp has changed (or if it's a brand new file).
                            if metadata.get(remote_full_path) != remote_mtime:
                                logger.info(f"Update: {remote_full_path} -> Downloading...")
                                
                                # Download the file and write it in binary mode ("wb")
                                with open(local_full_path, "wb") as f:
                                    ftp.retrbinary(f"RETR {remote_full_path}", f.write)
                                
                                # Update our memory with the new timestamp so we don't download it again tomorrow
                                metadata[remote_full_path] = remote_mtime
                                updated_files.append(local_full_path)
                            else:
                                logger.debug(f"Skipping unchanged remote file: {remote_full_path}")

            except Exception as e:
                logger.exception(f"Error while walking {remote_path}: {e}")

        # 2. Trigger the Recursive Walk starting from the root folder
        walk_recursive(remote_root, temp_folder)

        # ---------------------------------------------------------
        # 3. GHOST PURGE (Delete local files that were removed remotely)
        # ---------------------------------------------------------
        logger.debug("Starting Ghost Purge comparing local physical files with remote state...")
        
        # A. Delete orphaned physical files from the local hard drive
        for root, _, files in os.walk(temp_folder):
            for file_name in files:
                local_full_path = os.path.join(root, file_name)
                
                # Reconstruct the expected remote path for this local file
                rel_path = os.path.relpath(local_full_path, temp_folder).replace("\\", "/")
                
                # Ensure the path matches the structure of remote_root
                expected_remote_path = f"{remote_root.rstrip('/')}/{rel_path}"

                # If the local physical file is NOT in the list of files currently on the FTP...
                if expected_remote_path not in remote_files_found:
                    logger.info(f"Orphan physical file detected: {local_full_path} -> Deleting...")
                    try:
                        os.remove(local_full_path)
                    except Exception as e:
                        logger.error(f"Error deleting physical file {local_full_path}: {e}")

        # B. Clean the memory (metadata) of old references
        stored_paths = list(metadata.keys())
        for path_in_meta in stored_paths:
            if path_in_meta not in remote_files_found:
                logger.debug(f"Removing deleted file from memory: {path_in_meta}")
                del metadata[path_in_meta]

        # Close the connection politely
        ftp.quit()
        logger.debug(f"FTP sync downloaded {len(updated_files)} updated files")
        logger.info("FTP Sync completed successfully.")
        
        # Return the list of newly downloaded files and the updated memory state
        return updated_files, metadata

    except Exception as e:
        logger.exception(f"FTP fatal error: {e}")
        # If the server is offline or connection fails, return empty list 
        # but preserve the current metadata so we don't lose our memory.
        return [], metadata