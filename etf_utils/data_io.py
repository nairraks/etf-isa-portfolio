"""CSV/JSON helpers and SQLite-backed save/load for ETF pipeline data."""

import json
from pathlib import Path

import pandas as pd

from .config import DATA_CONFIG, DATA_INTERMEDIATE, DATA_OUTPUT, DATA_RAW
from .database import (
    PortfolioLockedError,
    load_portfolio,
    load_screened_etfs,
    save_portfolio,
    save_screened_etfs,
)

__all__ = [
    "get_region_category_from_filename",
    "get_asset_class_from_filename",
    "load_raw_etf_data",
    "save_intermediate",
    "load_intermediate",
    "save_output",
    "load_output",
    "load_config",
    "PortfolioLockedError",
]


# ---------------------------------------------------------------------------
# Filename parsers (unchanged — still used by notebook 01 summary cell)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Raw ETF data — still read from CSVs (notebook 01 summary cell uses file glob)
# ---------------------------------------------------------------------------

def load_raw_etf_data(pattern: str = "justetf_class-*.csv") -> dict[str, pd.DataFrame]:
    """Load all JustETF scrape CSVs matching *pattern* from data/raw/.

    Returns a dict mapping filename stem → DataFrame.
    """
    files = list(DATA_RAW.glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern!r} in {DATA_RAW}")
    return {f.stem: pd.read_csv(f) for f in sorted(files)}


# ---------------------------------------------------------------------------
# Intermediate data — DB-backed, with CSV backup
# ---------------------------------------------------------------------------

def _asset_class_from_intermediate_filename(filename: str) -> str:
    """Derive asset_class from filenames like 'summary_equities.csv' or 'summary_all.csv'."""
    stem = Path(filename).stem  # e.g. 'summary_equities'
    parts = stem.split("_", 1)
    suffix = parts[1] if len(parts) > 1 else stem  # 'equities', 'bonds', 'all', etc.
    # Normalise plurals so they match the asset_class values used in the DB
    mapping = {
        "equities":       "equity",
        "bonds":          "bonds",
        "preciousmetals": "preciousMetals",
        "preciousMetals": "preciousMetals",
        "commodities":    "commodities",
    }
    # Return "all" for unrecognised suffixes so callers skip DB operations
    # (avoids writing test data or ad-hoc filenames into the database).
    return mapping.get(suffix, "all")


def save_intermediate(df: pd.DataFrame, filename: str, portfolio_year: int = 2026) -> Path:
    """Save *df* to data/intermediate/{filename} (CSV) and to the DB.

    For combined files (summary_all.csv) only the CSV is written; individual
    asset-class saves are the source of truth in the DB.
    DB failures are non-fatal: a warning is issued and CSV is still written.
    """
    path = DATA_INTERMEDIATE / filename
    df.to_csv(path)  # keep index for CSV fallback compatibility

    asset_class = _asset_class_from_intermediate_filename(filename)
    if asset_class != "all":
        try:
            save_screened_etfs(df, asset_class, portfolio_year=portfolio_year)
        except Exception as exc:
            import warnings
            warnings.warn(f"[data_io] DB write skipped for {filename}: {exc}", stacklevel=2)

    return path


def load_intermediate(filename: str, portfolio_year: int = 2026) -> pd.DataFrame:
    """Load screened ETFs from DB; fall back to CSV if DB is empty or unavailable."""
    asset_class = _asset_class_from_intermediate_filename(filename)

    try:
        if asset_class == "all":
            df = load_screened_etfs(portfolio_year=portfolio_year)
        else:
            df = load_screened_etfs(asset_class=asset_class, portfolio_year=portfolio_year)
        if not df.empty:
            return df
    except Exception:
        pass  # DB unavailable — fall through to CSV

    path = DATA_INTERMEDIATE / filename
    if not path.exists():
        raise FileNotFoundError(f"Intermediate file not found: {path}")
    return pd.read_csv(path, index_col=0)


# ---------------------------------------------------------------------------
# Output / portfolio data — DB-backed, with CSV backup
# ---------------------------------------------------------------------------

def save_output(df: pd.DataFrame, filename: str, year: int = 2026) -> Path:
    """Save *df* to data/output/{filename} (CSV) and to the DB as portfolio *year*.

    DB failures are non-fatal: a warning is issued and CSV is still written.
    """
    path = DATA_OUTPUT / filename
    df.to_csv(path)  # keep index for CSV fallback compatibility
    try:
        save_portfolio(df, year=year)
    except Exception as exc:
        import warnings
        warnings.warn(f"[data_io] DB write skipped for {filename}: {exc}", stacklevel=2)
    return path


def load_output(filename: str, year: int = 2026) -> pd.DataFrame:
    """Load the portfolio for *year* from the DB; fall back to CSV if unavailable."""
    try:
        df = load_portfolio(year=year)
        if not df.empty:
            return df
    except Exception:
        pass  # DB unavailable — fall through to CSV

    path = DATA_OUTPUT / filename
    if not path.exists():
        raise FileNotFoundError(f"Output file not found: {path}")
    return pd.read_csv(path, index_col=0)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def load_config(filename: str) -> dict:
    """Load a JSON config file from data/config/{filename}."""
    path = DATA_CONFIG / filename
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with open(path) as f:
        return json.load(f)
