"""Path constants and environment config loading."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (two levels up from this file: etf_utils/ -> project root)
_PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

PROJECT_ROOT = _PROJECT_ROOT
DATA_RAW = PROJECT_ROOT / "data" / "raw"
DATA_INTERMEDIATE = PROJECT_ROOT / "data" / "intermediate"
DATA_OUTPUT = PROJECT_ROOT / "data" / "output"
DATA_CONFIG = PROJECT_ROOT / "data" / "config"

DATA_PROVIDER = os.getenv("DATA_PROVIDER", "yfinance")
ALPHAVANTAGE_API_KEY = os.getenv("ALPHAVANTAGE_API_KEY", "")
