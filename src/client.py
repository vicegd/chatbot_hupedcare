import requests
import colorama
import utils.logger as logger
from utils.helper import load_config

logger = logger.setup_logger(logger_name="api_client", log_filename="client.log")

# Initialize colorama (autoreset=True makes colors only apply to the current print)
colorama.init(autoreset=True)

def chat():
    """Run the interactive command-line client for the chatbot API.

    The client reloads the current server configuration, prints a small banner
    through the logging system, and then enters a request-response loop until
    the user submits an exit command or interrupts the session.
    """
    # Reload the config at startup so the CLI always uses the latest server URL.
    config = load_config()
    url = config['server']['public_url'] + "/ask"
    logger.debug(f"Client configured to use endpoint: {url}")
    
    # Route the CLI banner through the logger so all console output follows the same path.
    logger.info(colorama.Style.BRIGHT + colorama.Fore.CYAN + "=" * 50)
    logger.info(colorama.Style.BRIGHT + colorama.Fore.CYAN + "       HUPEDCARE CHATBOT - RESEARCH ASSISTANT")
    logger.info(colorama.Style.BRIGHT + colorama.Fore.CYAN + "=" * 50)
    logger.info(f"Connected to: {colorama.Fore.YELLOW}{url}")
    logger.info(f"Type {colorama.Fore.RED}'exit'{colorama.Fore.RESET} to close the session.\n")
    
    while True:
        try:
            # 1. USER INPUT (green color for user text)
            question = input(colorama.Style.BRIGHT + colorama.Fore.GREEN + ">> ")
            logger.debug(f"Received user input with length {len(question.strip())}")

            # Preserve the multilingual exit aliases already used by the CLI.
            if question.lower() in ["salir", "exit", "wyjść", "sair", "çıkmak", "quit"]:
                logger.info(colorama.Fore.YELLOW + "Closing session... Goodbye!")
                break
            
            if not question.strip():
                logger.debug("Skipping empty user input")
                continue

            logger.debug("Sending request to backend")

            # 2. API REQUEST
            response = requests.post(url, json={"question": question})
            logger.debug(f"Received HTTP status {response.status_code} from backend")

            if response.status_code == 200:
                # The API contract returns the generated answer under the 'response' key.
                answer = response.json()['response']
                logger.debug(f"Received answer with length {len(answer)}")
                # 3. AI RESPONSE (blue/cyan color for the assistant)
                logger.info(colorama.Style.BRIGHT + colorama.Fore.BLUE + "<< " + colorama.Style.NORMAL + colorama.Fore.WHITE + answer + "\n")
            else:
                logger.error(f"Server error: {response.status_code}")

        except KeyboardInterrupt:
            logger.info("Session interrupted by user.")
            break
        except Exception as e:
            logger.exception(f"Connection error: {e}")
            break

if __name__ == "__main__":
    logger.info("Starting API client...")
    chat()