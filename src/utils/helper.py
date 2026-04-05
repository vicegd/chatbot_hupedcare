from dotenv import load_dotenv
import os, re, base64, json, yaml
from bs4 import BeautifulSoup
import PyPDF2
from docx import Document
from openai import OpenAI
import subprocess
from docx import Document
import subprocess
import os
import json
import base64
from openai import OpenAI
from moviepy import VideoFileClip 

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

def save_metadata(metadata):
    METADATA_FILE = os.path.join(config['storage']['data_folder'], ".metadata.json")
    with open(METADATA_FILE, "w") as f:
        json.dump(metadata, f, indent=4)

load_dotenv()
config = load_config()
metadata = load_metadata()
client = OpenAI(base_url=config['ai']['base_url'], api_key=os.getenv("MODEL_API_KEY"))

def extract_clean_text(text):
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)

def extract_from_html_or_php(file_path):
    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    content = re.sub(r'<\?php.*?\?>', '', content, flags=re.DOTALL | re.IGNORECASE)
    soup = BeautifulSoup(content, 'html.parser')
    for tag in soup(["script", "style", "header", "footer", "nav", "aside"]):
        tag.decompose()
    return extract_clean_text(soup.get_text(separator=' '))

def extract_from_pdf(file_path):
    text = ""
    try:
        with open(file_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
    except Exception as e: print(f"PDF Error: {e}")
    return extract_clean_text(text)

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

def extract_description_from_video_with_ai(video_path):
    """
    Orchestrates the video analysis by using existing audio and image helpers.
    Ensures path compatibility to avoid 'File not found' errors.
    """
    #Normalize path to avoid issues with slashes or spaces
    video_path = os.path.abspath(video_path)
    temp_dir = os.path.dirname(video_path)
    
    try:
        #STEP 1: GET VIDEO DURATION
        duration_cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration", 
            "-of", "default=noprint_wrappers=1:nokey=1", video_path
        ]
        duration = float(subprocess.run(duration_cmd, capture_output=True, text=True).stdout.strip())
        timestamps = [duration * 0.2, duration * 0.5, duration * 0.8]

        #STEP 2: VISUAL ANALYSIS (Using your Image Helper)
        visual_contexts = []
        for i, ts in enumerate(timestamps):
            frame_path = os.path.join(temp_dir, f"temp_frame_{i}.jpg")
            
            #Extract frame using FFmpeg
            subprocess.run([
                "ffmpeg", "-ss", str(ts), "-i", video_path, 
                "-vframes", "1", "-q:v", "2", "-y", frame_path
            ], check=True, capture_output=True)
            
            print(f"  -> Calling Image Helper for frame at {int(ts)}s...")

            frame_description = extract_description_from_image_with_ai(frame_path)
            visual_contexts.append(f"Scene at {int(ts)}s: {frame_description}")
            
            if os.path.exists(frame_path):
                os.remove(frame_path)

        #STEP 3: AUDIO ANALYSIS
        audio_path = os.path.join(temp_dir, "temp_audio_extract.mp3")
        print(f"  -> Extracting audio stream...")
        subprocess.run([
            "ffmpeg", "-i", video_path, "-vn", "-ar", "16000", 
            "-ac", "1", "-b:a", "64k", "-y", audio_path
        ], check=True, capture_output=True)

        print(f"  -> Calling Audio Helper for full transcription...")
        full_transcription = extract_description_from_audio_with_ai(audio_path)
        
        if os.path.exists(audio_path):
            os.remove(audio_path)

        #STEP 4: FINAL SYNTHESIS (LLM)
        #We combine the results from your helpers into one cohesive story
        print(f"  -> Synthesizing final video narrative via {config['ai']['model']}...")
        
        visual_data = "\n".join(visual_contexts)
        synthesis_prompt = f"""
        Provide a professional English summary of this video based on the following processed data:

        TRANSCRIPTION:
        {full_transcription}

        VISUAL CHRONOLOGY:
        {visual_data}

        TASK: Write a cohesive paragraph explaining the video's core topic, 
        how the visuals align with the speech, and the overall objective of the content.
        """

        response = client.chat.completions.create(
            model=config['ai']['synthesis_model'],
            messages=[
                {"role": "system", "content": "You are a multimodal data analyst."},
                {"role": "user", "content": synthesis_prompt}
            ],
            temperature=0.4
        )

        return f"MULTIMODAL VIDEO SUMMARY:\n\n{response.choices[0].message.content}"

    except Exception as e:
        return f"Error in Video Pipeline: {str(e)}"

def extract_from_docx(file_path):
    """Extrae texto de archivos .docx modernos."""
    try:
        doc = Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        #Also tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    full_text.append(cell.text)
        return extract_clean_text("\n".join(full_text))
    except Exception as e:
        print(f"Error procesando DOCX {file_path}: {e}")
        return ""

def extract_from_doc(file_path):
    """
    Zero-dependency extractor for legacy .doc files.
    """
    try:
        with open(file_path, 'rb') as f:
            content = f.read()

        #1. Extract ASCII strings (sequences of 4+ printable characters)
        ascii_text = re.findall(rb'[\x20-\x7E]{4,}', content)
        decoded_ascii = " ".join([s.decode('ascii', errors='ignore') for s in ascii_text])

        #2. Extract UTF-16LE strings (Common in modern .doc for special chars/accents)
        #We look for patterns of [char][null] which is how UTF-16LE stores simple text
        utf16_text = re.findall(rb'(?:[\x20-\x7E]\x00){4,}', content)
        decoded_utf16 = " ".join([s.decode('utf-16le', errors='ignore') for s in utf16_text])

        #Combine both extractions
        combined_text = decoded_ascii + " " + decoded_utf16
        
        #3. Clean up typical Word binary "noise" (metadata, internal tags)
        #This removes common strings like 'Microsoft Word', 'Normal.dotm', etc.
        noise_patterns = [
            r'Microsoft\sWord', r'Normal\.dotm', r'Title', r'Subject', 
            r'Author', r'Keywords', r'Comments'
        ]
        for pattern in noise_patterns:
            combined_text = re.sub(pattern, '', combined_text, flags=re.I)

        #Use the existing cleaning helper
        return extract_clean_text(combined_text)

    except Exception as e:
        print(f"Binary scraper failed for {file_path}: {e}")
        return ""