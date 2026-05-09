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


# ── LLM (Groq) ─────────────────────────────────────────────────────────────
# Accept GROQ_API_KEY or the legacy LLM_API_KEY name — both work.
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

# ── SMTP ─────────────────────────────────────────────────────────────────────
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_SENDER_NAME: str = os.getenv("SMTP_SENDER_NAME", "Finance Department")

# ── Run mode ─────────────────────────────────────────────────────────────────
# DRY_RUN=true  → emails are printed/logged only, never sent via SMTP
DRY_RUN: bool = os.getenv("DRY_RUN", "true").strip().lower() == "true"

# ── Paths ────────────────────────────────────────────────────────────────────
DATA_PATH: str = str(BASE_DIR / "Dataset" / "Data_Ingestion.csv")
OUTPUT_DIR: str = str(BASE_DIR / "outputs")
