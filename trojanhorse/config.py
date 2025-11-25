"""Configuration management for TrojanHorse."""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """Configuration object with all user-defined paths and settings."""

    # Vault configuration
    vault_root: Path
    capture_dirs: List[Path]
    processed_root: Optional[Path]
    state_dir: Path

    # OpenRouter configuration
    openrouter_api_key: str
    openrouter_model: str

    # Embedding configuration
    embedding_model_name: str
    embedding_api_key: Optional[str]
    embedding_api_base: str

    @classmethod
    def from_env(cls) -> "Config":
        """Load configuration from environment variables."""
        # Required vault root
        vault_root_str = os.getenv("WORKVAULT_ROOT")
        if not vault_root_str:
            raise ValueError("WORKVAULT_ROOT environment variable is required")

        vault_root = Path(vault_root_str).resolve()
        if not vault_root.exists():
            raise ValueError(f"WORKVAULT_ROOT does not exist: {vault_root}")

        if not vault_root.is_dir():
            raise ValueError(f"WORKVAULT_ROOT is not a directory: {vault_root}")

        # Capture directories (relative to vault root)
        capture_dirs_str = os.getenv("WORKVAULT_CAPTURE_DIRS", "Inbox")
        capture_dirs = [
            vault_root / dir_name.strip()
            for dir_name in capture_dirs_str.split(",")
        ]

        # Optional processed root
        processed_root_str = os.getenv("WORKVAULT_PROCESSED_ROOT")
        processed_root = None
        if processed_root_str:
            processed_root = vault_root / processed_root_str.strip()

        # State directory
        state_dir_str = os.getenv("TROJANHORSE_STATE_DIR")
        if state_dir_str:
            state_dir = Path(state_dir_str).resolve()
        else:
            state_dir = Path.home() / ".trojanhorse"

        # OpenRouter configuration
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY", "")
        if not openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable is required")

        openrouter_model = os.getenv(
            "OPENROUTER_MODEL",
            "google/gemini-2.5-flash-lite-001"
        )

        # Embedding configuration
        embedding_model_name = os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-3-small")
        embedding_api_key = os.getenv("EMBEDDING_API_KEY")
        embedding_api_base = os.getenv(
            "EMBEDDING_API_BASE",
            "https://api.openai.com/v1"
        )

        logger.info(f"Configuration loaded - Vault: {vault_root}")
        logger.info(f"Capture dirs: {[d.name for d in capture_dirs]}")
        logger.info(f"State dir: {state_dir}")

        return cls(
            vault_root=vault_root,
            capture_dirs=capture_dirs,
            processed_root=processed_root,
            state_dir=state_dir,
            openrouter_api_key=openrouter_api_key,
            openrouter_model=openrouter_model,
            embedding_model_name=embedding_model_name,
            embedding_api_key=embedding_api_key,
            embedding_api_base=embedding_api_base,
        )

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        # Ensure capture directories exist
        for capture_dir in self.capture_dirs:
            capture_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured capture directory exists: {capture_dir}")

        # Ensure processed directory exists if configured
        if self.processed_root:
            self.processed_root.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Ensured processed directory exists: {self.processed_root}")

        # Ensure state directory exists
        self.state_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured state directory exists: {self.state_dir}")

    def validate(self) -> None:
        """Validate configuration and raise errors for issues."""
        # Check that capture dirs are subdirectories of vault root
        for capture_dir in self.capture_dirs:
            try:
                capture_dir.relative_to(self.vault_root)
            except ValueError:
                raise ValueError(
                    f"Capture directory {capture_dir} must be inside vault root {self.vault_root}"
                )

        # Check processed root is inside vault root if configured
        if self.processed_root:
            try:
                self.processed_root.relative_to(self.vault_root)
            except ValueError:
                raise ValueError(
                    f"Processed directory {self.processed_root} must be inside vault root {self.vault_root}"
                )