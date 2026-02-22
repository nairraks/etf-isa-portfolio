"""CSV and JSON helpers for reading/writing data files."""

import json
from pathlib import Path

import pandas as pd

from .config import DATA_CONFIG, DATA_INTERMEDIATE, DATA_OUTPUT, DATA_RAW


def get_region_category_from_filename(filename: str) -> str:
    """Parse ``justetf_class-{asset}_{market}_{region}.csv`` → ``{market}_{region}``."""
    stem = Path(filename).stem  # strip .csv
    parts = stem.split("_", 2)  # ['justetf', 'class-equity', 'developed_emea']
    return parts[2] if len(parts) > 2 else stem


def get_asset_class_from_filename(filename: str) -> str:
    """Parse ``justetf_class-{asset}_...csv`` → ``{asset}`` (e.g. 'equity', 'bonds')."""
    stem = Path(filename).stem
    parts = stem.split("-", 1)  # ['justetf_class', 'equity_developed_emea']
    if len(parts) > 1:
        return parts[1].split("_")[0]
    return stem


def load_raw_etf_data(pattern: str = "justetf_class-*.csv") -> dict[str, pd.DataFrame]:
    """Load all JustETF scrape CSVs matching *pattern* from data/raw/.

    Returns a dict mapping filename stem → DataFrame.
    """
    files = list(DATA_RAW.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern!r} in {DATA_RAW}")
    return {f.stem: pd.read_csv(f) for f in sorted(files)}


def save_intermediate(df: pd.DataFrame, filename: str) -> Path:
    """Save *df* to data/intermediate/{filename}. Returns the path written."""
    path = DATA_INTERMEDIATE / filename
    df.to_csv(path)
    return path


def load_intermediate(filename: str) -> pd.DataFrame:
    """Load a CSV from data/intermediate/{filename}."""
    path = DATA_INTERMEDIATE / filename
    if not path.exists():
        raise FileNotFoundError(f"Intermediate file not found: {path}")
    return pd.read_csv(path, index_col=0)


def save_output(df: pd.DataFrame, filename: str) -> Path:
    """Save *df* to data/output/{filename}. Returns the path written."""
    path = DATA_OUTPUT / filename
    df.to_csv(path)
    return path


def load_output(filename: str) -> pd.DataFrame:
    """Load a CSV from data/output/{filename}."""
    path = DATA_OUTPUT / filename
    if not path.exists():
        raise FileNotFoundError(f"Output file not found: {path}")
    return pd.read_csv(path, index_col=0)


def load_config(filename: str) -> dict:
    """Load a JSON config file from data/config/{filename}."""
    path = DATA_CONFIG / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return json.load(f)
