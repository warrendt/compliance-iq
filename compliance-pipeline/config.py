"""
Configuration for the compliance pipeline.
Loads settings from environment variables or .env file.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PipelineConfig:
    """Pipeline configuration loaded from environment."""

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_deployment: str = "gpt-4.1"
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_api_key: Optional[str] = None  # If not set, uses DefaultAzureCredential

    # Model settings
    max_tokens: int = 16000
    batch_size: int = 8  # Controls per LLM call for mapping

    # Pipeline settings
    min_confidence_threshold: float = 0.5  # Include mappings above this confidence
    include_low_confidence: bool = True  # Include low-confidence with warnings
    max_pdf_pages: int = 120  # Safety limit for PDF page count

    # Output
    output_dir: str = "./output"

    @classmethod
    def from_env(cls, env_file: Optional[str] = None) -> "PipelineConfig":
        """Load config from environment, optionally reading a .env file first."""
        if env_file:
            _load_dotenv(env_file)
        elif Path(".env").exists():
            _load_dotenv(".env")
        # Also check parent app/.env
        agent_env = Path(__file__).parent.parent / "app" / "backend" / ".env"
        if agent_env.exists():
            _load_dotenv(str(agent_env))

        return cls(
            azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
            azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME", "gpt-4.1"),
            azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-12-01-preview"),
            azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            max_tokens=int(os.getenv("AI_MAX_TOKENS", "16000")),
            batch_size=max(1, int(os.getenv("AI_BATCH_SIZE", "8"))),
            min_confidence_threshold=float(os.getenv("MIN_CONFIDENCE", "0.5")),
            include_low_confidence=os.getenv("INCLUDE_LOW_CONFIDENCE", "true").lower() == "true",
            max_pdf_pages=max(1, int(os.getenv("MAX_PDF_PAGES", "120"))),
            output_dir=os.getenv("OUTPUT_DIR", "./output"),
        )

    def validate(self) -> list[str]:
        """Return list of config validation errors (empty = valid)."""
        errors = []
        if not self.azure_openai_endpoint:
            errors.append("AZURE_OPENAI_ENDPOINT is required")
        if not self.azure_openai_deployment:
            errors.append("AZURE_OPENAI_DEPLOYMENT_NAME is required")
        return errors


def _load_dotenv(path: str):
    """Minimal .env loader — no external dependency needed."""
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip("\"'")
                if key and key not in os.environ:  # Don't override existing env vars
                    os.environ[key] = value
    except FileNotFoundError:
        pass
