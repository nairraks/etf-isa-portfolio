"""SQLite persistence layer for ETF portfolio data."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import pandas as pd

from .config import DATA_OUTPUT, DB_PATH


class PortfolioLockedError(Exception):
    """Raised when attempting to overwrite a locked (versioned) portfolio year."""


_db_initialized = False


def _ensure_init() -> None:
    global _db_initialized
    if not _db_initialized:
        init_db()
        _db_initialized = True


@contextmanager
def _get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create the portfolio_meta table.

    The three data tables (raw_etf_data, screened_etfs, portfolios) are created
    automatically by pandas ``to_sql`` on first write, so their schemas adapt to
    whatever columns the DataFrames contain.
    """
    with _get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS portfolio_meta (
                year        INTEGER PRIMARY KEY,
                is_locked   INTEGER NOT NULL DEFAULT 0,
                locked_at   TEXT,
                created_at  TEXT NOT NULL,
                notes       TEXT
            );
        """)


# ---------------------------------------------------------------------------
# Raw ETF data (replaces data/raw/justetf_class-*.csv in the DB)
# ---------------------------------------------------------------------------

def save_raw_etf_data(df: pd.DataFrame, asset_class: str, region_category: str) -> None:
    """Replace raw ETF rows for (asset_class, region_category) with *df*.

    Uses a read-modify-write strategy (replace whole table) so that schema
    changes between runs (e.g. JustETF adding or removing columns) never cause
    an ``if_exists='append'`` mismatch error.
    """
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()
    df = df.copy()
    df["asset_class"] = asset_class
    df["region_category"] = region_category
    df["scraped_at"] = now

    with _get_connection() as conn:
        # Load rows for all OTHER (asset_class, region_category) combos.
        # If the table doesn't exist yet, start with an empty frame.
        try:
            existing = pd.read_sql(
                "SELECT * FROM raw_etf_data WHERE asset_class != ? OR region_category != ?",
                conn,
                params=[asset_class, region_category],
            )
        except Exception:
            existing = pd.DataFrame()

        combined = pd.concat([existing, df], ignore_index=True) if not existing.empty else df
        combined.to_sql("raw_etf_data", conn, if_exists="replace", index=False)


def load_raw_etf_data(
    asset_class: str | None = None,
    region_category: str | None = None,
) -> pd.DataFrame:
    """Query raw_etf_data. Optionally filter by asset_class and/or region_category."""
    _ensure_init()
    clauses, params = [], []
    if asset_class is not None:
        clauses.append("asset_class = ?")
        params.append(asset_class)
    if region_category is not None:
        clauses.append("region_category = ?")
        params.append(region_category)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM raw_etf_data {where}"  # noqa: S608

    with _get_connection() as conn:
        df = pd.read_sql(query, conn, params=params)

    return df.drop(columns=["_row_id"], errors="ignore")


# ---------------------------------------------------------------------------
# Screened ETFs (replaces data/intermediate/summary_*.csv)
# ---------------------------------------------------------------------------

def save_screened_etfs(
    df: pd.DataFrame,
    asset_class: str,
    portfolio_year: int = 2026,
) -> None:
    """Replace screened ETF rows for (portfolio_year, asset_class) with *df*."""
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()
    df = df.copy()
    df["portfolio_year"] = portfolio_year
    df["asset_class"] = asset_class
    df["screened_at"] = now

    with _get_connection() as conn:
        try:
            existing = pd.read_sql(
                "SELECT * FROM screened_etfs WHERE portfolio_year != ? OR asset_class != ?",
                conn,
                params=[portfolio_year, asset_class],
            )
        except Exception:
            existing = pd.DataFrame()

        combined = pd.concat([existing, df], ignore_index=True) if not existing.empty else df
        combined.to_sql("screened_etfs", conn, if_exists="replace", index=False)


def load_screened_etfs(
    asset_class: str | None = None,
    portfolio_year: int = 2026,
) -> pd.DataFrame:
    """Load screened ETFs for *portfolio_year*, optionally filtered by *asset_class*."""
    _ensure_init()
    params: list = [portfolio_year]
    asset_clause = ""
    if asset_class is not None:
        asset_clause = "AND asset_class = ?"
        params.append(asset_class)

    query = f"""
        SELECT * FROM screened_etfs
        WHERE portfolio_year = ? {asset_clause}
    """  # noqa: S608

    with _get_connection() as conn:
        df = pd.read_sql(query, conn, params=params)

    return df.drop(columns=["_row_id", "portfolio_year", "screened_at"], errors="ignore")


# ---------------------------------------------------------------------------
# Portfolio (replaces data/output/final_portfolio.csv, with versioning)
# ---------------------------------------------------------------------------

def save_portfolio(df: pd.DataFrame, year: int = 2026) -> None:
    """Save portfolio for *year*, raising PortfolioLockedError if the year is locked."""
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()

    with _get_connection() as conn:
        row = conn.execute(
            "SELECT is_locked FROM portfolio_meta WHERE year = ?", (year,)
        ).fetchone()
        if row and row[0]:
            raise PortfolioLockedError(
                f"Portfolio year {year} is locked and cannot be overwritten. "
                "Call lock_portfolio() only when you are ready to version a year."
            )

        df = df.copy()
        df["portfolio_year"] = year
        df["created_at"] = now

        try:
            conn.execute("DELETE FROM portfolios WHERE portfolio_year = ?", (year,))
        except sqlite3.OperationalError:
            pass  # table doesn't exist yet; to_sql will create it
        df.to_sql("portfolios", conn, if_exists="append", index=False)

        conn.execute(
            """
            INSERT INTO portfolio_meta (year, is_locked, created_at)
            VALUES (?, 0, ?)
            ON CONFLICT(year) DO UPDATE SET created_at=excluded.created_at
            """,
            (year, now),
        )


def load_portfolio(year: int = 2026) -> pd.DataFrame:
    """Load the portfolio for *year*. Returns an empty DataFrame if not found."""
    _ensure_init()
    try:
        with _get_connection() as conn:
            df = pd.read_sql(
                "SELECT * FROM portfolios WHERE portfolio_year = ?",  # noqa: S608
                conn,
                params=[year],
            )
    except Exception:
        return pd.DataFrame()
    return df.drop(columns=["_row_id", "portfolio_year", "created_at"], errors="ignore")


def lock_portfolio(year: int, notes: str = "") -> None:
    """Permanently lock *year* so it can never be overwritten."""
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()
    with _get_connection() as conn:
        existing = conn.execute(
            "SELECT year FROM portfolio_meta WHERE year = ?", (year,)
        ).fetchone()
        if not existing:
            raise ValueError(
                f"No portfolio found for year {year}. Save it first with save_portfolio()."
            )
        conn.execute(
            """
            UPDATE portfolio_meta
            SET is_locked=1, locked_at=?, notes=?
            WHERE year=?
            """,
            (now, notes, year),
        )


def list_portfolio_versions() -> list[dict]:
    """Return metadata for all saved portfolio years."""
    _ensure_init()
    with _get_connection() as conn:
        rows = conn.execute(
            "SELECT year, is_locked, locked_at, created_at, notes FROM portfolio_meta ORDER BY year"
        ).fetchall()
    return [
        {
            "year": r[0],
            "is_locked": bool(r[1]),
            "locked_at": r[2],
            "created_at": r[3],
            "notes": r[4],
        }
        for r in rows
    ]


def seed_2025_portfolio() -> None:
    """One-time import of the 2025 (FY25-26) portfolio into the DB as a locked version.

    Reads ``data/output/final_portfolio_25.csv`` if it exists, otherwise falls back to
    ``data/output/final_portfolio.csv``.  No-op if year 2025 is already in the DB.
    """
    _ensure_init()
    with _get_connection() as conn:
        existing = conn.execute(
            "SELECT year FROM portfolio_meta WHERE year = 2025"
        ).fetchone()
    if existing:
        return  # already seeded — idempotent

    for candidate in ("final_portfolio_25.csv", "final_portfolio.csv"):
        path = DATA_OUTPUT / candidate
        if path.exists():
            df = pd.read_csv(path)
            save_portfolio(df, year=2025)
            lock_portfolio(2025, notes=f"Seeded from {candidate} (FY 2025-26 equity/bond portfolio)")
            print(f"[database] Seeded 2025 portfolio from {candidate} and locked it.")
            return

    print("[database] Warning: no source CSV found to seed 2025 portfolio.")
