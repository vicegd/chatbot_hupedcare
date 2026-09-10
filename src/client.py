"""
=============================================================================
RAG COMMAND-LINE CLIENT (El "Terminal de Pruebas")
=============================================================================

This module provides a fast, interactive Command-Line Interface (CLI) to talk 
to your FastAPI server. It acts exactly like your frontend website, but runs 
entirely in the terminal.

Why this script is useful:
-----------------------------------------------------------------------------
1. ISOLATED TESTING: If the web frontend is broken, you can use this script 
   to verify if the Python backend is still working correctly.
2. COLOR-CODED UI: It uses `colorama` to paint the terminal with specific 
   colors (Green for You, Blue/White for the AI) making it highly readable.
3. GRACEFUL HANDLING: It catches connection errors gracefully. If the server 
   is turned off, the client won't crash with a massive block of red Python 
   errors; it will simply say "Connection error" and close politely.
4. MULTILINGUAL EXIT: It recognizes exit commands in several languages, making 
   it friendly for international developers.
=============================================================================
"""

import requests
import colorama
import utils.logger as logger
from utils.helper import load_config

# Initialize the logger for the client interface
logger = logger.setup_logger(logger_name="api_client", log_filename="client.log")

# Initialize colorama (autoreset=True ensures that a color applied to one 
# line doesn't accidentally bleed into the next line)
colorama.init(autoreset=True)


def resolve_api_endpoints(server_config):
    """Build a prioritized list of /ask endpoints from server URL settings."""
    base_urls = []

    public_urls = server_config.get('public_urls')
    if isinstance(public_urls, list):
        for url in public_urls:
            if isinstance(url, str) and url.strip():
                base_urls.append(url.strip().rstrip('/'))

    if not base_urls:
        raise ValueError(
            "server.public_urls must contain at least one base URL in config/config.yaml"
        )

    # Preserve order while removing duplicates.
    unique_base_urls = []
    for url in base_urls:
        if url not in unique_base_urls:
            unique_base_urls.append(url)

    return [f"{url}/ask" for url in unique_base_urls]

def chat():
    """
    Run the interactive command-line client for the chatbot API.

    The client reloads the current server configuration, prints a small banner
    through the logging system, and then enters a request-response loop until
    the user submits an exit command or interrupts the session.
    """
    # ---------------------------------------------------------
    # 1. CONFIGURATION AND URL RESOLUTION
    # ---------------------------------------------------------
    # Reload the config at startup so the CLI always uses the latest server URL.
    config = load_config()
    
    # Support multiple external URLs with graceful fallback.
    endpoints = resolve_api_endpoints(config['server'])
    primary_endpoint = endpoints[0]

    logger.debug(f"Client configured endpoints (priority order): {endpoints}")
    
    # ---------------------------------------------------------
    # 2. RENDER THE CLI BANNER
    # ---------------------------------------------------------
    # Route the CLI banner through the logger so all console output follows the same path.
    logger.info(colorama.Style.BRIGHT + colorama.Fore.CYAN + "=" * 50)
    logger.info(colorama.Style.BRIGHT + colorama.Fore.CYAN + "       HUPEDCARE CHATBOT - RESEARCH ASSISTANT")
    logger.info(colorama.Style.BRIGHT + colorama.Fore.CYAN + "=" * 50)
    logger.info(f"Primary endpoint: {colorama.Fore.YELLOW}{primary_endpoint}")
    if len(endpoints) > 1:
        logger.info(f"Fallback endpoints: {colorama.Fore.YELLOW}{', '.join(endpoints[1:])}")
    logger.info(f"Type {colorama.Fore.RED}'exit'{colorama.Fore.RESET} to close the session.\n")
    
    # ---------------------------------------------------------
    # 3. THE REPL LOOP (Read-Eval-Print Loop)
    # ---------------------------------------------------------
    while True:
        try:
            # A. USER INPUT (Rendered in Bright Green)
            question = input(colorama.Style.BRIGHT + colorama.Fore.GREEN + ">> ")
            logger.debug(f"Received user input with length {len(question.strip())}")

            # Preserve the multilingual exit aliases. If the user types any of these, stop the loop.
            if question.lower() in ["salir", "exit", "wyjść", "sair", "çıkmak", "quit"]:
                logger.info(colorama.Fore.YELLOW + "Closing session... Goodbye!")
                break
            
            # Prevent sending empty requests to the server
            if not question.strip():
                logger.debug("Skipping empty user input")
                continue

            logger.debug("Sending request to backend")

            # B. API REQUEST
            # Send the question as a JSON payload to the FastAPI server
            response = None
            last_connection_error = None
            selected_endpoint = None

            for endpoint in endpoints:
                try:
                    response = requests.post(endpoint, json={"question": question}, timeout=30)
                    selected_endpoint = endpoint
                    logger.debug(f"Received HTTP status {response.status_code} from {endpoint}")
                    break
                except requests.exceptions.ConnectionError as error:
                    last_connection_error = error
                    logger.warning(f"Endpoint unavailable, trying next: {endpoint}")

            if response is None:
                raise requests.exceptions.ConnectionError(last_connection_error)

            # C. PROCESS AND DISPLAY RESPONSE
            if response.status_code == 200:
                # The API contract returns the generated answer under the 'response' key.
                answer = response.json().get('response', 'No response provided by server.')
                logger.debug(f"Received answer with length {len(answer)}")
                logger.debug(f"Answer served from endpoint: {selected_endpoint}")
                
                # Render the AI's response (Blue for the arrows, White for the actual text)
                logger.info(
                    colorama.Style.BRIGHT + colorama.Fore.BLUE + "<< " + 
                    colorama.Style.NORMAL + colorama.Fore.WHITE + answer + "\n"
                )
            else:
                # Handle HTTP errors (like 404 Not Found or 500 Internal Server Error)
                logger.error(f"Server error: Received HTTP {response.status_code}")

        except KeyboardInterrupt:
            # Catches the user pressing [Ctrl+C] and exits cleanly instead of crashing
            logger.info("Session interrupted by user (Ctrl+C).")
            break
        except requests.exceptions.ConnectionError:
            # Explains what happens if the FastAPI server isn't running
            logger.error(colorama.Fore.RED + "Connection Error: Could not reach the server. Is server.py running?")
            break
        except Exception as e:
            # Catch-all for any other unexpected errors
            logger.exception(f"Unexpected connection error: {e}")
            break

# =============================================================================
# EXECUTION ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    logger.info("Starting API client...")
    chat()