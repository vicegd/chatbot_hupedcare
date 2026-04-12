import base64
import json
import os
import re
import yaml
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import PyPDF2
from docx import Document
from openai import OpenAI

# Initialization
config_path = None
project_root = None

def load_config():
    global config_path, project_root
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(base_dir, '..', '..'))
    config_path = os.path.join(project_root, 'config', 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as file_handle:
        return yaml.safe_load(file_handle)
    
def load_metadata():
    metadata_file_path = os.path.join(config['storage']['data_folder'], ".metadata.json")
    if os.path.exists(metadata_file_path):
        with open(metadata_file_path, "r") as file_handle:
            return json.load(file_handle)
    return {}

def save_metadata(metadata):
    metadata_file_path = os.path.join(config['storage']['data_folder'], ".metadata.json")
    with open(metadata_file_path, "w") as file_handle:
        json.dump(metadata, file_handle, indent=4)

load_dotenv()
config = load_config()
config['storage']['data_folder'] = os.path.join(project_root, 'DATA')
metadata = load_metadata()
client = OpenAI(base_url=config['ai']['base_url'], api_key=os.getenv("MODEL_API_KEY"))

def extract_clean_text(raw_text):
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    return "\n".join(lines)

def extract_from_html_or_php(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as file_handle:
        content = file_handle.read()
    content = re.sub(r'<\?php.*?\?>', '', content, flags=re.DOTALL | re.IGNORECASE)
    soup = BeautifulSoup(content, 'html.parser')
    for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
        tag.decompose()
    return extract_clean_text(soup.get_text(separator=' '))

def extract_from_pdf(file_path):
    extracted_text = ""
    try:
        with open(file_path, "rb") as file_handle:
            reader = PyPDF2.PdfReader(file_handle)
            for page in reader.pages:
                extracted_text += page.extract_text() + "\n"
    except Exception as e: print(f"PDF Error: {e}")
    return extract_clean_text(extracted_text)

def extract_description_from_image_with_ai(image_path):
    try:
        with open(image_path, "rb") as img:
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
    except Exception as e: return f"Vision Error: {e}"

def extract_description_from_audio_with_ai(audio_path):
    try:
        print(f"  -> Sending audio to Whisper...")
        with open(audio_path, "rb") as audio_file:
            transcription = client.audio.transcriptions.create(
                model=config['ai']['transcription_model'], 
                file=audio_file
            ).text
            
        return f"AUDIO TRANSCRIPTION: {transcription}"
    except Exception as e:
        print(f"Audio Error in {audio_path}: {e}")
        return "Error transcribing audio content."

def extract_from_docx(file_path):
    """Extract text from modern .docx files."""
    try:
        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    full_text.append(cell.text)
        return extract_clean_text("\n".join(full_text))
    except Exception as e:
        print(f"Error processing DOCX {file_path}: {e}")
        return ""

def extract_from_doc(file_path):
    """
    Zero-dependency extractor for legacy .doc files.
    """
    try:
        with open(file_path, 'rb') as file_handle:
            content = file_handle.read()

        # 1. Extract ASCII strings (sequences of 4+ printable characters).
        ascii_text = re.findall(rb'[\x20-\x7E]{4,}', content)
        decoded_ascii = " ".join([s.decode('ascii', errors='ignore') for s in ascii_text])

        # 2. Extract UTF-16LE strings, which are common in modern .doc files.
        # Look for [char][null] patterns, the usual UTF-16LE layout for simple text.
        utf16_text = re.findall(rb'(?:[\x20-\x7E]\x00){4,}', content)
        decoded_utf16 = " ".join([s.decode('utf-16le', errors='ignore') for s in utf16_text])

        # Combine both extraction strategies.
        combined_text = decoded_ascii + " " + decoded_utf16
        
        # 3. Remove typical Word binary noise such as metadata and internal tags.
        noise_patterns = [
            r'Microsoft\sWord', r'Normal\.dotm', r'Title', r'Subject', 
            r'Author', r'Keywords', r'Comments'
        ]
        for pattern in noise_patterns:
            combined_text = re.sub(pattern, '', combined_text, flags=re.I)

        # Reuse the common text cleanup helper.
        return extract_clean_text(combined_text)

    except Exception as e:
        print(f"Binary scraper failed for {file_path}: {e}")
        return ""