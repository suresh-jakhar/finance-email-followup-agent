"""
src/config.py

Loads environment variables from .env and exposes typed constants
used across every module in the project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve project root (two levels up from this file: src/ -> project root)
BASE_DIR: Path = Path(__file__).resolve().parent.parent

# Load .env from project root; silently no-ops if file is absent
load_dotenv(BASE_DIR / ".env")


def _require(key: str) -> str:
    """Return env var value or raise a clear error if it is missing."""
    value = os.getenv(key)
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{key}' is not set. "
            f"Copy .env.example to .env and fill in your values."
        )
    return value


# ── LLM ──────────────────────────────────────────────────────────────────────
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")

# ── SMTP ─────────────────────────────────────────────────────────────────────
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

# ── Run mode ─────────────────────────────────────────────────────────────────
# DRY_RUN=true  → emails are printed/logged only, never sent via SMTP
DRY_RUN: bool = os.getenv("DRY_RUN", "true").strip().lower() == "true"

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_PATH: str = str(BASE_DIR / "Dataset" / "Data_Ingestion.csv")
OUTPUT_DIR: str = str(BASE_DIR / "outputs")
