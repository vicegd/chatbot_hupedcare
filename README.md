# Multimodal RAG Data Collector: High-Efficiency Pipeline

This repository contains an advanced data ingestion system for RAG (Retrieval-Augmented Generation). The system is designed to synchronize, extract, and process information from multiple sources (FTP, MySQL) and formats (Text, Images, Video) to feed Large Language Models (LLM) such as Llama 3.3 70B.

## Key Features

- Incremental FTP Synchronization: Recursive mirroring from external servers (e.g., Hostinger) using MDTM commands to download only new or modified files.
- Database Ingestion: Automated record extraction from MySQL for structured data integration.
- Intelligent Multimodal Processing:
    * Text/Web: Clean extraction from HTML and PHP (removing boilerplate and server-side code blocks).
    * Vision: Detailed descriptions and OCR generation using Llama-4-Scout-17B.
    * Video: Audio transcription via Whisper-v3 and visual analysis of keyframes.
- Context Optimization (Token Efficiency):
    * Processing Cache: Prevents redundant processing of multimedia assets by using a local state-check.
    * Global Deduplication: Sentence-level filtering across all sources to maximize context window and reduce API costs.

## Repository Structure

```text
/
├── src/
│   ├── main.py                # Main workflow orchestrator
│   ├── ftp_collector.py       # Remote sync module (FTP)
│   ├── mysql_collector.py     # Database extraction module
│   └── collector_helper.py    # File processors (PDF, Images, Video)
├── docs/                     # Scientific Paper (LaTeX)
│   ├── main.tex               # Main article document
│   ├── references.bib         # Study bibliography
│   └── /figures               # Diagrams and charts
├── config/
│   └── config.yaml            # Configuration file
├── data/                      # (Ignored by Git)
│   ├── TEMP_DOWNLOADS/        # Local mirror
│   ├── CACHE_TEXT/            # Processed text versions
│   └── master_context.txt     # Final consolidated context
├── .env.example               # Template for environment variables
├── .gitignore                 # Git ignore rules
├── LICENSE                    # Project license
└── requirements.txt           # Python dependencies
```

## Installation & Setup

1. Clone the repository:

```bash
    git clone https://github.com/vicegd/chatbot_hupedcare
    cd chatbot_hupedcare
```

2. Install dependencies:
```bash
    pip install -r requirements.txt
```

3. Environment Configuration:
   - Create a .env file based on .env.example.
   - Add your API Keys (Groq/OpenAI) and server credentials (FTP/MySQL).
   - Adjust parameters in config/config.yaml.

4. Run the collection process:
```bash
    python src/main.py
```

## License

This project is licensed under the [MIT License](LICENSE).