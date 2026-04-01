import os, re, base64, json, yaml
from datetime import datetime
from bs4 import BeautifulSoup
import PyPDF2
from docx import Document
from moviepy import VideoFileClip
from openai import OpenAI

#Initialization
def load_config():
    with open("./config/config.yaml", "r") as f:
        return yaml.safe_load(f)
    
def load_metadata():
    METADATA_FILE = os.path.join(config['storage']['data_folder'], ".metadata.json")
    if os.path.exists(METADATA_FILE):
        with open(METADATA_FILE, "r") as f:
            return json.load(f)
    return {}

config = load_config()
metadata = load_metadata()
model = OpenAI(base_url=config['ai']['base_url'], api_key=os.getenv("MODEL_API_KEY"))

def clean_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def extract_from_html_or_php(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    content = re.sub(r'<\?php.*?\?>', '', content, flags=re.DOTALL | re.IGNORECASE)
    soup = BeautifulSoup(content, 'html.parser')
    for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
        tag.decompose()
    return clean_text(soup.get_text(separator=' '))

def extract_from_pdf(file_path):
    text = ""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e: print(f"PDF Error: {e}")
    return clean_text(text)

def describe_image_with_ai(image_path):
    try:
        with open(image_path, "rb") as img:
            b64_img = base64.b64encode(img.read()).decode('utf-8')
        response = model.chat.completions.create(
            model=config['ai']['vision_model'],
            messages=[{"role": "user", "content": [
                {"type": "text", "text": "Describe this image in detail for a RAG system. Transcribe any text."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
            ]}],
            max_tokens=300
        )
        return response.choices[0].message.content
    except Exception as e: return f"Vision Error: {e}"

def process_video_with_ai(video_path):
    try:
        clip = VideoFileClip(video_path)
        audio_path = video_path + ".mp3"
        clip.audio.write_audiofile(audio_path, logger=None)
        with open(audio_path, "rb") as f:
            transcription = model.audio.transcriptions.create(model="whisper-large-v3", file=f).text
        
        frame_path = video_path + "_snap.jpg"
        clip.save_frame(frame_path, t=clip.duration/2)
        visual_desc = describe_image_with_ai(frame_path)
        
        os.remove(audio_path); os.remove(frame_path)
        return f"VIDEO VISUAL: {visual_desc}\nTRANSCRIPTION: {transcription}"
    except Exception as e: return f"Video Error: {e}"