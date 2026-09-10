from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Optional, Protocol

import utils.helper as helper


class ExtractionStrategy(Protocol):
    """
    Strategy interface for modality-specific extraction.
    
    By defining a Protocol, we enforce a strict contract: any class 
    acting as a strategy must implement the 'extract' method. This allows 
    the system to remain decoupled from the specific extraction logic.
    """

    def extract(self, file_path: str) -> str:
        ...


class HtmlPhpExtractionStrategy:
    """Strategy for extracting clean text from web-based documents."""
    def extract(self, file_path: str) -> str:
        return helper.extract_from_html_or_php(file_path)


class ImageExtractionStrategy:
    """
    Strategy for Vision-Language abstraction. 
    Routes image files to a multimodal AI model to generate semantic descriptions.
    """
    def extract(self, file_path: str) -> str:
        return helper.extract_description_from_image_with_ai(file_path)


class AudioExtractionStrategy:
    """
    Strategy for Acoustic Modeling. 
    Routes audio files to an ASR (Automatic Speech Recognition) engine for transcription.
    """
    def extract(self, file_path: str) -> str:
        return helper.extract_description_from_audio_with_ai(file_path)


class DocxExtractionStrategy:
    """Strategy for extracting text and structure from modern Office documents."""
    def extract(self, file_path: str) -> str:
        return helper.extract_from_docx(file_path)


class DocExtractionStrategy:
    """Strategy for handling legacy binary Office documents (.doc)."""
    def extract(self, file_path: str) -> str:
        return helper.extract_from_doc(file_path)


class PdfExtractionStrategy:
    """Strategy for parsing PDF files, retaining structural integrity."""
    def extract(self, file_path: str) -> str:
        return helper.extract_from_pdf(file_path)


class TxtExtractionStrategy:
    """Strategy for reading plain text files safely using UTF-8 encoding."""
    def extract(self, file_path: str) -> str:
        # We ignore encoding errors to ensure the pipeline doesn't crash on malformed bytes
        with open(file_path, "r", encoding="utf-8", errors="ignore") as file_handle:
            return helper.extract_clean_text(file_handle.read())


class ExtractionStrategyRegistry:
    """
    Extension-based strategy resolver.
    
    This class acts as a central registry that maps file extensions to their 
    corresponding extraction strategies, avoiding massive if/else chains.
    """

    def __init__(self, mapping: Dict[str, ExtractionStrategy]) -> None:
        # Normalize all extensions to lowercase upon initialization to ensure case-insensitive matching
        self._mapping = {ext.lower(): strategy for ext, strategy in mapping.items()}

    def resolve(self, file_path: str) -> Optional[ExtractionStrategy]:
        """
        Extracts the file extension from the path and returns the appropriate strategy.
        Returns None if the extension is not supported by the current registry.
        """
        extension = Path(file_path).suffix.lower()
        return self._mapping.get(extension)


def build_default_registry() -> ExtractionStrategyRegistry:
    """
    Factory function to build and configure the default strategy registry.
    
    Strategies that share the same underlying logic (like HTML/PHP or various 
    image/audio formats) share the same strategy instance to conserve memory.
    """
    html = HtmlPhpExtractionStrategy()
    image = ImageExtractionStrategy()
    audio = AudioExtractionStrategy()
    
    return ExtractionStrategyRegistry(
        {
            ".html": html,
            ".htm": html,
            ".php": html,
            ".jpg": image,
            ".jpeg": image,
            ".png": image,
            ".webp": image,
            ".mp3": audio,
            ".wav": audio,
            ".m4a": audio,
            ".flac": audio,
            ".docx": DocxExtractionStrategy(),
            ".doc": DocExtractionStrategy(),
            ".pdf": PdfExtractionStrategy(),
            ".txt": TxtExtractionStrategy(),
        }
    )


def supported_extensions(registry: ExtractionStrategyRegistry) -> Iterable[str]:
    """Utility function to retrieve a tuple of all file extensions currently supported by the registry."""
    return tuple(registry._mapping.keys())