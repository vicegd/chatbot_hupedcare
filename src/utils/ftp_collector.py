import os
from ftplib import FTP

import utils.logger as logger

logger = logger.setup_logger(logger_name="ftp_collector", log_filename="ftp_collector.log")

def sync_ftp_files(metadata, temp_folder):
    """
    Synchronize the local temporary mirror with the remote FTP tree.

    Args:
        metadata: Dictionary that tracks the latest known remote modification
            timestamp for each synchronized file.
        temp_folder: Local folder where remote files are mirrored.

    Returns:
        A tuple `(updated_files, metadata)` where `updated_files` contains the
        local file paths downloaded during the current run and `metadata`
        contains the refreshed timestamp mapping.
    """
    updated_files = []
    remote_files_found = set()
    
    # Only mirror the file types that have downstream extractors in the RAG pipeline.
    VALID_EXTENSIONS = (
        ".html", ".htm", ".php", ".txt", ".pdf", ".docx", 
        ".doc",".jpg", ".jpeg", ".png", ".mp3", ".wav", ".m4a", ".flac"
    )

    try:
        host = os.getenv("FTP_HOST")
        logger.info(f"Connecting to FTP: {host}")
        logger.debug(f"FTP sync target folder: {temp_folder}")
        
        ftp = FTP(host)
        ftp.login(user=os.getenv("FTP_USER"), passwd=os.getenv("FTP_PASSWORD"))
        
        remote_root = os.getenv("FTP_REMOTE_PATH", "/")
        ftp.cwd(remote_root)
        logger.debug(f"FTP remote root set to {remote_root}")

        def walk_recursive(remote_path, local_path):
            """Internal helper to navigate FTP folders and download files."""
            if not os.path.exists(local_path):
                os.makedirs(local_path)

            try:
                # MLSD provides directory entries plus metadata in one round-trip.
                for name, facts in ftp.mlsd(path=remote_path):
                    if name in (".", ".."): 
                        continue

                    remote_full_path = os.path.join(remote_path, name).replace("\\", "/")
                    local_full_path = os.path.join(local_path, name)

                    if facts['type'] == 'dir':
                        # Recurse into child directories to mirror the full remote tree.
                        logger.debug(f"Descending into FTP directory: {remote_full_path}")
                        walk_recursive(remote_full_path, local_full_path)
                    
                    elif facts['type'] == 'file':
                        if name.lower().endswith(VALID_EXTENSIONS):
                            remote_files_found.add(remote_full_path)
                            logger.debug(f"Eligible remote file found: {remote_full_path}")

                            # MLSD exposes the server modification timestamp in the 'modify' field.
                            remote_mtime = facts.get('modify')

                            # Fallback to MDTM for older FTP servers that do not expose MLSD metadata.
                            if not remote_mtime:
                                response = ftp.sendcmd(f"MDTM {remote_full_path}")
                                remote_mtime = response[4:]

                            # Download only when the remote timestamp differs from the tracked metadata.
                            if metadata.get(remote_full_path) != remote_mtime:
                                logger.info(f"Update: {remote_full_path} -> Downloading...")
                                
                                with open(local_full_path, "wb") as f:
                                    ftp.retrbinary(f"RETR {remote_full_path}", f.write)
                                
                                metadata[remote_full_path] = remote_mtime
                                updated_files.append(local_full_path)
                            else:
                                logger.debug(f"Skipping unchanged remote file: {remote_full_path}")

            except Exception as e:
                logger.exception(f"Error while walking {remote_path}: {e}")

        # Mirror the remote subtree under the configured local temp folder.
        walk_recursive(remote_root, temp_folder)

        # Remove local files that disappeared upstream and clear their metadata entries.
        stored_paths = list(metadata.keys())
        logger.debug(f"Metadata entries tracked before cleanup: {len(stored_paths)}")
        for path_in_meta in stored_paths:
            if path_in_meta not in remote_files_found:
                logger.info(f"Was first deleted on server: {path_in_meta} -> Cleaning local copy...")
                
                rel_path = os.path.relpath(path_in_meta, remote_root)
                local_to_delete = os.path.join(temp_folder, rel_path)
                
                if os.path.exists(local_to_delete):
                    try:
                        os.remove(local_to_delete)
                    except Exception as e:
                        logger.error(f"Error deleting {local_to_delete}: {e}")

                del metadata[path_in_meta]

        ftp.quit()
        logger.debug(f"FTP sync downloaded {len(updated_files)} updated files")
        logger.info("FTP Sync completed successfully.")
        return updated_files, metadata

    except Exception as e:
        logger.exception(f"FTP fatal error: {e}")
        return [], metadata