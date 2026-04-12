import requests
from colorama import Fore, Style, init
from utils.helper import load_config
import utils.logger as logger

logger = logger.setup_logger(logger_name="api_client", log_filename="client.log")

# Initialize colorama (autoreset=True makes colors only apply to the current print)
init(autoreset=True)

def chat():
    config = load_config()
    url = config['server']['public_url'] + "/ask"
    logger.debug(f"Client configured to use endpoint: {url}")
    
    logger.info(Style.BRIGHT + Fore.CYAN + "=" * 50)
    logger.info(Style.BRIGHT + Fore.CYAN + "       HUPEDCARE CHATBOT - RESEARCH ASSISTANT")
    logger.info(Style.BRIGHT + Fore.CYAN + "=" * 50)
    logger.info(f"Connected to: {Fore.YELLOW}{url}")
    logger.info(f"Type {Fore.RED}'exit'{Fore.RESET} to close the session.\n")
    
    while True:
        try:
            # 1. USER INPUT (green color for user text)
            question = input(Style.BRIGHT + Fore.GREEN + ">> ")
            logger.debug(f"Received user input with length {len(question.strip())}")

            if question.lower() in ["salir", "exit", "wyjść", "sair", "çıkmak", "quit"]:
                logger.info(Fore.YELLOW + "Closing session... Goodbye!")
                break
            
            if not question.strip():
                logger.debug("Skipping empty user input")
                continue

            logger.debug("Sending request to backend")

            # 2. API REQUEST
            response = requests.post(url, json={"question": question})
            logger.debug(f"Received HTTP status {response.status_code} from backend")

            if response.status_code == 200:
                answer = response.json()['response']
                logger.debug(f"Received answer with length {len(answer)}")
                # 3. AI RESPONSE (blue/cyan color for the assistant)
                logger.info(Style.BRIGHT + Fore.BLUE + "<< " + Style.NORMAL + Fore.WHITE + answer + "\n")
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