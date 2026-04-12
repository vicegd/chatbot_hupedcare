import requests
import sys
from colorama import Fore, Style, init
from utils.helper import load_config
import utils.logger as logger

logger = logger.setup_logger(logger_name="api_client", log_filename="client.log")

# Initialize colorama (autoreset=True makes colors only apply to the current print)
init(autoreset=True)

def chat():
    config = load_config()
    url = config['server']['public_url'] + "/ask"
    
    # Header
    print(Style.BRIGHT + Fore.CYAN + "="*50)
    print(Style.BRIGHT + Fore.CYAN + "       HUPEDCARE CHATBOT - RESEARCH ASSISTANT")
    print(Style.BRIGHT + Fore.CYAN + "="*50)
    print(f"Connected to: {Fore.YELLOW}{url}")
    print(f"Type {Fore.RED}'exit'{Fore.RESET} to close the session.\n")
    
    while True:
        try:
            # 1. USER INPUT (green color for user text)
            print(Style.BRIGHT + Fore.GREEN + ">>", end=" ")
            question = input()

            if question.lower() in ["salir", "exit", "wyjść", "sair", "çıkmak", "quit"]:
                print(Fore.YELLOW + "\nClosing session... Goodbye!")
                break
            
            if not question.strip():
                continue

            # Visual feedback while waiting
            print(Fore.MAGENTA + "Thinking...", end="\r")

            # 2. API REQUEST
            response = requests.post(url, json={"question": question})
            
            # Clear "Thinking..." line
            sys.stdout.write("\033[K") 

            if response.status_code == 200:
                answer = response.json()['response']
                # 3. AI RESPONSE (blue/cyan color for the assistant)
                print(Style.BRIGHT + Fore.BLUE + "<< " + Style.NORMAL + Fore.WHITE + answer + "\n")
            else:
                print(Fore.RED + f"Server Error: {response.status_code}")

        except KeyboardInterrupt:
            logger.error("Session interrupted by user.")
            print(Fore.YELLOW + "\n\nSession interrupted by user.")
            break
        except Exception as e:
            logger.error(f"Connection error: {e}")
            print(Fore.RED + f"\nConnection error: {e}")
            break

if __name__ == "__main__":
    logger.info("Starting API client...")
    chat()