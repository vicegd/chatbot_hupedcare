"""
=============================================================================
RAG UTILITY & EXTRACTION HELPER
=============================================================================

This module acts as the "Swiss Army Knife" for the entire RAG project. It 
centralizes two critical responsibilities:

1. GLOBAL STATE MANAGEMENT:
   It dynamically locates the root of the project, loads the `config.yaml`, 
   and manages the `.metadata.json` state. By doing this here, other scripts 
   (like server.py or collector.py) don't have to guess where files are saved.

2. MULTI-MODAL DATA EXTRACTION:
   It contains specialized functions to crack open almost any file format and 
   extract pure, clean text from it. This is the core of the RAG system: turning 
   messy human files into clean strings that the AI can read.

Supported Formats & Strategies:
-----------------------------------------------------------------------------
- .PDF / .DOCX : Uses native Python libraries to extract text and tables.
- .DOC (Legacy) : Uses a clever binary-scraping fallback to rescue text from 
                  old 1990s/2000s Microsoft Word files without needing Word installed.
- .HTML / .PHP  : Uses BeautifulSoup to strip away website code (navbars, scripts) 
                  and keep only the article content.
- Images (.JPG) : Converts the image to Base64 and asks an AI Vision model to 
                  describe it in text format.
- Audio (.MP3)  : Sends the audio to a Speech-to-Text model (like Whisper) to 
                  get a perfect transcription.
=============================================================================
"""

import base64
import json
import os
import re

import PyPDF2
import yaml
from bs4 import BeautifulSoup
from docx import Document
from dotenv import load_dotenv
from openai import OpenAI

import utils.logger as logger

# Initialize the logger for the helper functions
logger = logger.setup_logger(logger_name="helper", log_filename="helper.log")

# Global variables to store paths so they are calculated only once
config_path = None
project_root = None

def load_config():
    """
    Locates and loads the config.yaml file.
    
    Why this is robust: 
    It calculates the path relative to THIS file's location. This means it doesn't 
    matter if you run the code from the '/src' folder, the root folder, or via a cronjob; 
    it will always find the 'config' directory correctly.
    """
    global config_path, project_root
    
    # Go up two levels from src/utils/helper.py to find the project root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, '..', '..'))
    config_path = os.path.join(project_root, 'config', 'config.yaml')
    
    logger.debug(f"Loading configuration from {config_path}")
    with open(config_path, 'r', encoding='utf-8') as file_handle:
        return yaml.safe_load(file_handle)
    
def load_metadata():
    """
    Loads the '.metadata.json' file which keeps track of what the collector 
    has already processed (like the master_context_hash).
    If the file doesn't exist yet (e.g., first run), it returns an empty dictionary.
    """
    metadata_file_path = os.path.join(config['storage']['data_folder'], ".metadata.json")
    logger.debug(f"Loading metadata from {metadata_file_path}")
    
    if os.path.exists(metadata_file_path):
        with open(metadata_file_path, "r") as file_handle:
            return json.load(file_handle)
    return {}

def save_metadata(metadata):
    """
    Saves the current state of the collector back to '.metadata.json'.
    This allows the system to "remember" its state between executions.
    """
    metadata_file_path = os.path.join(config['storage']['data_folder'], ".metadata.json")
    logger.debug(f"Saving metadata to {metadata_file_path}")
    
    with open(metadata_file_path, "w") as file_handle:
        # indent=4 makes the JSON file human-readable
        json.dump(metadata, file_handle, indent=4)

# =============================================================================
# BOOTSTRAP: Initialize the environment immediately when this module is imported
# =============================================================================
load_dotenv() # Load environment variables (like API keys) from the .env file
config = load_config()

# Force the data folder path to be absolute, ensuring all data goes to the root /DATA
config['storage']['data_folder'] = os.path.join(project_root, config['storage']['data_folder'])

metadata = load_metadata()

# Initialize the OpenAI-compatible client. 
# Because we use config['ai']['base_url'], this seamlessly supports Open Source 
# models hosted on Together AI, Groq, or local servers.
client = OpenAI(
    base_url=config['ai']['base_url'], 
    api_key=os.getenv("MODEL_API_KEY")
)
logger.debug(f"Resolved storage data directory to {config['storage']['data_folder']}")

# =============================================================================
# DATA EXTRACTION PIPELINES
# =============================================================================

def extract_clean_text(raw_text):
    """
    Normalizes text by removing empty lines and excessive spaces.
    
    Why: AI models perform better and cost less (fewer tokens) when the 
    context doesn't contain hundreds of useless blank lines or weird spacing.
    """
    logger.debug(f"Extracting clean text from raw text: {raw_text[:100]}...")
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return "\n".join(lines)

def extract_from_html_or_php(file_path):
    """
    Extracts purely the readable article/text from a web page file.
    It strips out code, styles, navigation bars, and footers.
    """
    logger.debug(f"Extracting text from HTML/PHP file: {file_path}")
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file_handle:
        content = file_handle.read()
        
    # Remove backend PHP code blocks entirely so the AI doesn't read the server logic
    content = re.sub(r'<\?php.*?\?>', '', content, flags=re.DOTALL | re.IGNORECASE)
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # Destroy HTML tags that contain layout/styling but no useful knowledge
    for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
        tag.decompose()
        
    return extract_clean_text(soup.get_text(separator=' '))

def extract_from_pdf(file_path):
    """
    Extracts raw text from a PDF document page by page.
    """
    extracted_text = ""
    try:
        logger.debug(f"Extracting text from PDF file: {file_path}")
        with open(file_path, "rb") as file_handle:
            reader = PyPDF2.PdfReader(file_handle)
            for page in reader.pages:
                extracted_text += page.extract_text() + "\n"
    except Exception as e:
        logger.exception(f"PDF extraction error for {file_path}: {e}")
    return extract_clean_text(extracted_text)

def extract_description_from_image_with_ai(image_path):
    """
    Acts as the 'eyes' of the system. It converts an image to Base64, sends it 
    to the Vision AI model, and asks it to write a detailed text description.
    This allows the Chatbot to 'search' inside images later.
    """
    try:
        logger.debug(f"Generating AI description for image: {image_path}")
        with open(image_path, "rb") as img:
            # The Vision API requires the image to be converted into a Base64 string
            b64_img = base64.b64encode(img.read()).decode('utf-8')
            
        response = client.chat.completions.create(
            model=config['ai']['vision_model'],
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe this image in detail for a RAG system. Transcribe any text."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
            ]}],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.exception(f"Image description error for {image_path}: {e}")
        return f"Vision Error: {e}"

def extract_description_from_audio_with_ai(audio_path):
    """
    Acts as the 'ears' of the system. Uses Speech-to-Text models (like Whisper) 
    to transcribe audio files (like podcasts or voice notes) into text.
    """
    try:
        logger.debug(f"Sending audio file to transcription model: {audio_path}")
        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model=config['ai']['transcription_model'], 
                file=audio_file
            ).text
            
        return f"AUDIO TRANSCRIPTION: {transcription}"
    except Exception as e:
        logger.exception(f"Audio transcription error for {audio_path}: {e}")
        return "Error transcribing audio content."

def extract_from_docx(file_path):
    """
    Extracts text from modern Microsoft Word (.docx) files.
    It reads both standard paragraphs and data hidden inside tables.
    """
    try:
        logger.debug(f"Extracting text from DOCX file: {file_path}")
        doc = Document(file_path)
        full_text = []
        
        # 1. Extract normal text blocks
        for para in doc.paragraphs:
            full_text.append(para.text)
            
        # 2. Extract text from inside grids and tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    full_text.append(cell.text)
                    
        return extract_clean_text("\n".join(full_text))
    except Exception as e:
        logger.exception(f"DOCX extraction error for {file_path}: {e}")
        return ""

def extract_from_doc(file_path):
    """
    A heuristic "rescue" parser for legacy binary `.doc` files (Word 97-2003).
    
    Why this is useful: 
    Instead of requiring Microsoft Office or expensive anti-word tools installed 
    on the Linux server, it scrapes the binary file looking for ASCII and UTF-16 
    string patterns, bypassing the proprietary format entirely.
    """
    try:
        logger.debug(f"Extracting text from legacy DOC file: {file_path}")
        with open(file_path, 'rb') as file_handle:
            content = file_handle.read()

        # 1. Scrape for ASCII strings (Standard English/Basic characters)
        ascii_text = re.findall(rb'[\x20-\x7E]{4,}', content)
        decoded_ascii = " ".join([s.decode('ascii', errors='ignore') for s in ascii_text])

        # 2. Scrape for UTF-16LE strings (Characters with accents, symbols, modern Word)
        utf16_text = re.findall(rb'(?:[\x20-\x7E]\x00){4,}', content)
        decoded_utf16 = " ".join([s.decode('utf-16le', errors='ignore') for s in utf16_text])

        # Merge both findings
        combined_text = decoded_ascii + " " + decoded_utf16
        
        # 3. Clean up the mess. The binary scraping catches Word's internal metadata.
        # We use Regex to hunt down and delete these useless system tags.
        noise_patterns = [
            r'Microsoft\sWord', r'Normal\.dotm', r'Title', r'Subject', 
            r'Author', r'Keywords', r'Comments'
        ]
        for pattern in noise_patterns:
            combined_text = re.sub(pattern, '', combined_text, flags=re.I)

        return extract_clean_text(combined_text)

    except Exception as e:
        logger.exception(f"Legacy DOC extraction error for {file_path}: {e}")
        return ""