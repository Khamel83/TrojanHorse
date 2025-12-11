"""TrojanHorse: Local Vault Processor + Q&A

A minimal, local-first system that watches folders, processes new text/markdown files,
classifies them using LLMs, writes structured notes, and provides RAG-based Q&A.
"""

__version__ = "0.2.0"

from .config import Config
from .models import NoteMeta
from .processor import Processor
from .rag import rebuild_index, query
from .meeting_synthesizer import MeetingSynthesizer

__all__ = [
    "Config",
    "NoteMeta",
    "Processor",
    "rebuild_index",
    "query",
    "MeetingSynthesizer",
]