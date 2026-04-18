"""SQLite persistence layer for ETF portfolio data."""

import sqlite3
import time
import random
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
    # timeout=60: wait up to 60 s if another process (e.g. cloud-sync) holds a lock.
    # WAL mode is intentionally NOT used because the DB often lives on Google Drive /
    # OneDrive / Dropbox, which cannot reliably handle WAL shared-memory files
    # (.db-wal / .db-shm), causing intermittent "database is locked" / "Execution
    # failed" errors.  The default DELETE journal mode is safe for our single-writer,
    # sequential-notebook use case.
    conn = sqlite3.connect(DB_PATH, timeout=60)
    try:
        yield conn
        # Retry commit if it fails due to locking
        for i in range(5):
            try:
                conn.commit()
                break
            except sqlite3.OperationalError as e:
                if i < 4 and ("locked" in str(e).lower() or "execution failed" in str(e).lower()):
                    time.sleep(0.5 * (2 ** i) + random.uniform(0, 0.1))
                    continue
                raise
    except Exception:
        try:
            conn.rollback()
        except sqlite3.OperationalError:
            pass # ignore errors during rollback
        raise
    finally:
        conn.close()


def _execute_with_retry(func, *args, **kwargs):
    """Execution wrapper that retries on SQLite 'database is locked' errors."""
    for i in range(5):
        try:
            return func(*args, **kwargs)
        except sqlite3.OperationalError as e:
            if i < 4 and ("locked" in str(e).lower() or "execution failed" in str(e).lower()):
                time.sleep(0.5 * (2 ** i) + random.uniform(0, 0.1))
                continue
            raise


def init_db() -> None:
    """Create the portfolio_meta table.

    The three data tables (raw_etf_data, screened_etfs, portfolios) are created
    automatically by pandas ``to_sql`` on first write, so their schemas adapt to
    whatever columns the DataFrames contain.
    """
    def _do_init():
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
    _execute_with_retry(_do_init)


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

    def _do_save():
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

    _execute_with_retry(_do_save)


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

    def _do_load():
        with _get_connection() as conn:
            return pd.read_sql(query, conn, params=params)

    df = _execute_with_retry(_do_load)
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

    def _do_save():
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

    _execute_with_retry(_do_save)


# ---------------------------------------------------------------------------
# Benchmark ETFs (replaces data/intermediate/benchmark_distributing_df_*.csv)
# ---------------------------------------------------------------------------

def save_benchmark_etfs(
    df: pd.DataFrame,
    asset_class: str,
    portfolio_year: int = 2026,
) -> None:
    """Replace benchmark ETF rows for (portfolio_year, asset_class) with *df*.

    Stores the pre-filter audit trail — all distributing ETFs with beta
    calculated, before the top-N cut.  Replaces the old
    ``benchmark_distributing_df_*.csv`` files.
    """
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()
    df = df.copy()
    df["portfolio_year"] = portfolio_year
    df["asset_class"] = asset_class
    df["saved_at"] = now

    def _do_save():
        with _get_connection() as conn:
            try:
                existing = pd.read_sql(
                    "SELECT * FROM benchmark_etfs WHERE portfolio_year != ? OR asset_class != ?",
                    conn,
                    params=[portfolio_year, asset_class],
                )
            except Exception:
                existing = pd.DataFrame()

            combined = pd.concat([existing, df], ignore_index=True) if not existing.empty else df
            combined.to_sql("benchmark_etfs", conn, if_exists="replace", index=False)

    _execute_with_retry(_do_save)


def load_benchmark_etfs(
    asset_class: str | None = None,
    portfolio_year: int = 2026,
) -> pd.DataFrame:
    """Load benchmark ETFs for *portfolio_year*, optionally filtered by *asset_class*."""
    _ensure_init()
    params: list = [portfolio_year]
    asset_clause = ""
    if asset_class is not None:
        asset_clause = "AND asset_class = ?"
        params.append(asset_class)

    query = f"""
        SELECT * FROM benchmark_etfs
        WHERE portfolio_year = ? {asset_clause}
    """  # noqa: S608

    def _do_load():
        with _get_connection() as conn:
            try:
                return pd.read_sql(query, conn, params=params)
            except Exception:
                return pd.DataFrame()

    df = _execute_with_retry(_do_load)
    return df.drop(columns=["_row_id", "portfolio_year", "saved_at"], errors="ignore")


# ---------------------------------------------------------------------------
# Rebalancing trades (parsed InvestEngine trading statements)
# ---------------------------------------------------------------------------

def save_rebalancing_trades(df: pd.DataFrame, portfolio_year: int) -> None:
    """Replace rebalancing trade rows for *portfolio_year* with *df*.

    Stores the parsed trading statement (after ISIN extraction, ticker mapping,
    signed quantities, etc.).  Keyed by portfolio_year so each year's trades
    can be loaded independently.
    """
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()
    df = df.copy()
    df["portfolio_year"] = portfolio_year
    df["saved_at"] = now

    # SQLite has no native datetime; pandas read_sql brings dates back as
    # strings. Mixing those strings with fresh Timestamp values via concat
    # makes to_sql fail with "type 'Timestamp' is not supported". Coerce
    # any datetime-like columns to ISO strings before persisting.
    for col in df.select_dtypes(include=["datetime", "datetimetz"]).columns:
        df[col] = df[col].dt.strftime("%Y-%m-%d %H:%M:%S")
    # Also handle Timestamps hiding in object-dtype columns (e.g. after
    # concat with existing string data from SQLite).
    for col in df.select_dtypes(include=["object"]).columns:
        if df[col].apply(lambda v: isinstance(v, pd.Timestamp)).any():
            df[col] = df[col].apply(
                lambda v: v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, pd.Timestamp) else v
            )

    def _do_save():
        with _get_connection() as conn:
            try:
                existing = pd.read_sql(
                    "SELECT * FROM rebalancing_trades WHERE portfolio_year != ?",
                    conn,
                    params=[portfolio_year],
                )
            except Exception:
                existing = pd.DataFrame()

            combined = pd.concat([existing, df], ignore_index=True) if not existing.empty else df
            combined.to_sql("rebalancing_trades", conn, if_exists="replace", index=False)

    _execute_with_retry(_do_save)


def load_rebalancing_trades(portfolio_year: int) -> pd.DataFrame:
    """Load rebalancing trades for *portfolio_year*. Returns empty DataFrame if not found."""
    _ensure_init()
    def _do_load():
        with _get_connection() as conn:
            try:
                return pd.read_sql(
                    "SELECT * FROM rebalancing_trades WHERE portfolio_year = ?",  # noqa: S608
                    conn,
                    params=[portfolio_year],
                )
            except Exception:
                return pd.DataFrame()

    df = _execute_with_retry(_do_load)
    return df.drop(columns=["_row_id", "portfolio_year", "saved_at"], errors="ignore")


def purge_screened_etfs_for_year(portfolio_year: int = 2026) -> int:
    """Delete ALL screened ETF rows for *portfolio_year*.

    Useful after changing the portfolio model (e.g. adding/removing asset classes)
    to avoid stale rows causing KeyErrors in sr_data_map lookups.
    Returns the number of rows deleted.
    """
    _ensure_init()
    def _do_purge():
        with _get_connection() as conn:
            cur = conn.execute(
                "DELETE FROM screened_etfs WHERE portfolio_year = ?",
                (portfolio_year,),
            )
            return cur.rowcount
    return _execute_with_retry(_do_purge)


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

    def _do_load():
        with _get_connection() as conn:
            return pd.read_sql(query, conn, params=params)

    df = _execute_with_retry(_do_load)
    return df.drop(columns=["_row_id", "portfolio_year", "screened_at"], errors="ignore")


# ---------------------------------------------------------------------------
# Portfolio (replaces data/output/final_portfolio.csv, with versioning)
# ---------------------------------------------------------------------------

def save_portfolio(df: pd.DataFrame, year: int = 2026) -> None:
    """Save portfolio for *year*, raising PortfolioLockedError if the year is locked."""
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()

    def _do_save():
        with _get_connection() as conn:
            row = conn.execute(
                "SELECT is_locked FROM portfolio_meta WHERE year = ?", (year,)
            ).fetchone()
            if row and row[0]:
                raise PortfolioLockedError(
                    f"Portfolio year {year} is locked and cannot be overwritten. "
                    "Call lock_portfolio() only when you are ready to version a year."
                )

            df_local = df.copy() # Avoid modifying outside scope
            df_local["portfolio_year"] = year
            df_local["created_at"] = now

            # Read-modify-write: preserve other years' rows and handle schema changes
            # (e.g. new columns added to the ETF data) without OperationalError.
            # Mirrors the strategy used by save_screened_etfs / save_raw_etf_data.
            try:
                existing = pd.read_sql(
                    "SELECT * FROM portfolios WHERE portfolio_year != ?",
                    conn,
                    params=[year],
                )
            except Exception:
                existing = pd.DataFrame()

            combined = pd.concat([existing, df_local], ignore_index=True) if not existing.empty else df_local
            combined.to_sql("portfolios", conn, if_exists="replace", index=False)

            conn.execute(
                """
                INSERT INTO portfolio_meta (year, is_locked, created_at)
                VALUES (?, 0, ?)
                ON CONFLICT(year) DO UPDATE SET created_at=excluded.created_at
                """,
                (year, now),
            )

    _execute_with_retry(_do_save)


def load_portfolio(year: int = 2026) -> pd.DataFrame:
    """Load the portfolio for *year*. Returns an empty DataFrame if not found."""
    _ensure_init()
    def _do_load():
        with _get_connection() as conn:
            return pd.read_sql(
                "SELECT * FROM portfolios WHERE portfolio_year = ?",  # noqa: S608
                conn,
                params=[year],
            )
    
    try:
        df = _execute_with_retry(_do_load)
    except Exception:
        return pd.DataFrame()
    return df.drop(columns=["_row_id", "portfolio_year", "created_at"], errors="ignore")


def lock_portfolio(year: int, notes: str = "") -> None:
    """Permanently lock *year* so it can never be overwritten."""
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()
    def _do_lock():
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
    _execute_with_retry(_do_lock)


def list_portfolio_versions() -> list[dict]:
    """Return metadata for all saved portfolio years."""
    _ensure_init()
    def _do_list():
        with _get_connection() as conn:
            return conn.execute(
                "SELECT year, is_locked, locked_at, created_at, notes FROM portfolio_meta ORDER BY year"
            ).fetchall()
            
    rows = _execute_with_retry(_do_list)
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

# ---------------------------------------------------------------------------
# Trading 212 Instruments Cache
# ---------------------------------------------------------------------------

def save_trading212_instruments(df: pd.DataFrame) -> None:
    """Save Trading 212 instruments to the database as a cache."""
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()
    df = df.copy()
    df["cached_at"] = now
    def _do_save():
        with _get_connection() as conn:
            df.to_sql("trading212_instruments", conn, if_exists="replace", index=False)

    _execute_with_retry(_do_save)


def load_trading212_instruments() -> pd.DataFrame:
    """Load Trading 212 instruments from the cache table. Returns empty DataFrame if not found."""
    _ensure_init()
    def _do_load():
        with _get_connection() as conn:
            return pd.read_sql("SELECT * FROM trading212_instruments", conn)
            
    try:
        df = _execute_with_retry(_do_load)
    except Exception:
        return pd.DataFrame()
    return df.drop(columns=["_row_id", "cached_at"], errors="ignore")


# ---------------------------------------------------------------------------
# InvestEngine Instruments Cache
# ---------------------------------------------------------------------------

def save_investengine_instruments(df: pd.DataFrame) -> None:
    """Save InvestEngine instruments to the database as a cache."""
    _ensure_init()
    now = datetime.now(timezone.utc).isoformat()
    df = df.copy()
    df["cached_at"] = now
    def _do_save():
        with _get_connection() as conn:
            df.to_sql("investengine_instruments", conn, if_exists="replace", index=False)

    _execute_with_retry(_do_save)


def load_investengine_instruments() -> pd.DataFrame:
    """Load InvestEngine instruments from the cache table. Returns empty DataFrame if not found."""
    _ensure_init()
    def _do_load():
        with _get_connection() as conn:
            return pd.read_sql("SELECT * FROM investengine_instruments", conn)
            
    try:
        df = _execute_with_retry(_do_load)
    except Exception:
        return pd.DataFrame()
    return df.drop(columns=["_row_id", "cached_at"], errors="ignore")
