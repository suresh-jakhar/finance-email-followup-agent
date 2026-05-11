import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR: Path = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


GROQ_API_KEY: str = os.getenv("GROQ_API_KEY") or os.getenv("LLM_API_KEY", "")
LLM_MODEL: str = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")

# SMTP
SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER: str = os.getenv("SMTP_USER", "")
SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
SMTP_SENDER_NAME: str = os.getenv("SMTP_SENDER_NAME", "Finance Department")
PAYMENT_LINK: str = os.getenv("PAYMENT_LINK", "https://payments.example.com/portal")
BANK_DETAILS: str = os.getenv("BANK_DETAILS", "IBAN: GB00 0000 0000 0000 | SWIFT: EXAMPLEX")
                    

DRY_RUN: bool = os.getenv("DRY_RUN", "true").strip().lower() == "true"

# Automated Scheduling
_raw_time = os.getenv("SCHEDULE_HOUR", "9:00")
if ":" in _raw_time:
    _parts = _raw_time.split(":")
    SCHEDULE_HOUR: int = int(_parts[0])
    SCHEDULE_MINUTE: int = int(_parts[1])
else:
    SCHEDULE_HOUR: int = int(_raw_time)
    SCHEDULE_MINUTE: int = 0

TIMEZONE: str = os.getenv("TIMEZONE", "Asia/Kolkata")

DATA_PATH: str = str(BASE_DIR / "Dataset" / "Data_Ingestion.csv")
OUTPUT_DIR: str = str(BASE_DIR / "outputs")
