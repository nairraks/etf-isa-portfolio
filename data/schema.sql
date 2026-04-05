-- =============================================================================
-- ETF ISA Portfolio Database Schema
-- File:    data/etf_portfolio.db
-- Updated: 2026-04-05
-- Recovery: delete DB and re-run notebooks 01 → 02 → 03 in order, or:
--           git checkout data/etf_portfolio.db
-- =============================================================================

-- ---------------------------------------------------------------------------
-- TABLE: portfolio_meta
-- Purpose: Version lock metadata — one row per portfolio construction year.
--          Controls whether save_portfolio() can overwrite a given year.
-- Written by: database.init_db(), database.lock_portfolio()
-- Read by:    database.save_portfolio() (checks is_locked before write)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS portfolio_meta (
    year       INTEGER PRIMARY KEY,  -- Portfolio year (e.g. 2025, 2026)
    is_locked  INTEGER NOT NULL DEFAULT 0,  -- 1 = frozen, 0 = mutable
    locked_at  TEXT,    -- ISO-8601 UTC timestamp when locked, NULL if still mutable
    created_at TEXT NOT NULL,  -- ISO-8601 UTC timestamp of row creation
    notes      TEXT     -- Optional free-text annotation (e.g. "2025 initial build")
);

-- ---------------------------------------------------------------------------
-- TABLE: raw_etf_data
-- Purpose: Raw JustETF scrape outputs — one row per ETF per (asset_class, region).
--          This is the pipeline entry point; populated by notebook 01.
-- Written by: database.save_raw_etf_data(df, asset_class, region_category)
-- Read by:    notebook 02 (via load_raw_etf_data)
-- Key filters: asset_class IN ('equity','bonds','preciousMetals','commodities')
--              region_category: 'developed_americasanduk', 'developed_apac',
--                               'developed_emea', 'emerging_americas',
--                               'emerging_apacandemea', 'global'
-- Note: Created lazily by pandas to_sql on first write. Columns adapt to
--       whatever the JustETF scraper returns.
-- ---------------------------------------------------------------------------
CREATE TABLE raw_etf_data (
    -- Metadata columns (always present)
    asset_class      TEXT,  -- Asset class: equity | bonds | preciousMetals | commodities
    region_category  TEXT,  -- JustETF region slug (see Key filters above)
    scraped_at       TEXT,  -- ISO-8601 UTC timestamp of scrape

    -- Identity columns (from JustETF)
    ticker  TEXT,  -- LSE ticker without exchange suffix (e.g. 'VEVE', 'SLXX')
    isin    TEXT,  -- ISIN (e.g. 'IE00B1W57M07')
    name    TEXT,  -- Full fund name
    wkn     TEXT,  -- German securities ID
    valor   TEXT,  -- Swiss securities ID

    -- Fund characteristics
    ter              REAL,  -- Total expense ratio (e.g. 0.0022 = 0.22%)
    size             REAL,  -- AUM in EUR millions
    currency         TEXT,  -- Fund base currency (GBP, EUR, USD)
    domicile_country TEXT,  -- Fund domicile (Ireland, Luxembourg, etc.)
    inception_date   TEXT,  -- Fund launch date (YYYY-MM-DD)
    age_in_days      REAL,
    age_in_years     REAL,
    replication      TEXT,  -- Physical | Synthetic | Optimised sampling
    hedged           INTEGER,  -- 0 = unhedged, 1 = currency hedged
    is_sustainable   INTEGER,  -- 0/1 ESG flag
    securities_lending INTEGER,
    strategy         TEXT,
    dividends        TEXT,  -- Distributing | Accumulating
    number_of_holdings INTEGER,

    -- Return columns (decimal fractions, e.g. 0.12 = 12%)
    last_week        REAL,
    yesterday        REAL,
    last_month       REAL,
    last_three_months REAL,
    last_six_months  REAL,
    last_year        REAL,  -- Trailing 12-month return (most reliable)
    last_three_years REAL,
    last_five_years  REAL,
    "2021" REAL,  -- Calendar year returns
    "2022" REAL,
    "2023" REAL,
    "2024" REAL,
    "2025" REAL,

    -- Risk columns
    last_year_volatility        REAL,
    last_three_years_volatility REAL,
    last_five_years_volatility  REAL,
    max_drawdown                REAL,
    last_year_max_drawdown      REAL,
    last_three_years_max_drawdown REAL,
    last_five_years_max_drawdown  REAL,

    -- Risk-adjusted return columns (return / volatility)
    last_year_return_per_risk        REAL,
    last_three_years_return_per_risk REAL,
    last_five_years_return_per_risk  REAL,

    -- Dividend
    last_dividends       REAL,
    last_year_dividends  REAL,

    -- Live price (fetched at scrape time via yfinance)
    yday_close_price_date TEXT,
    yday_close_price      REAL   -- GBP per share
);

-- ---------------------------------------------------------------------------
-- TABLE: screened_etfs
-- Purpose: Top-ranked ETFs after screening — one row per selected ETF per
--          (portfolio_year, asset_class). Replaces summary_*.csv files.
--          Contains all raw_etf_data columns plus screening-derived fields.
-- Written by: database.save_screened_etfs(df, asset_class, portfolio_year)
-- Read by:    notebook 03 via load_screened_etfs(portfolio_year)
-- Typical row count: 2–5 per (portfolio_year, asset_class)
-- ---------------------------------------------------------------------------
CREATE TABLE screened_etfs (
    -- Inherits all raw_etf_data columns (see above) plus:
    portfolio_year  INTEGER,  -- e.g. 2026
    asset_class     TEXT,     -- Redundant with raw but explicit for queries
    screened_at     TEXT,     -- ISO-8601 UTC timestamp

    -- Screening-derived columns (added by notebook 02)
    region           TEXT,    -- Broad region label (e.g. 'Developed Americas & UK')
    country          TEXT,    -- Country / sub-region
    intra_region_category TEXT,  -- For intra-class weighting
    benchmark_ticker TEXT,   -- Benchmark ETF ticker used for beta calc (e.g. 'VEVE')
    benchmark_description TEXT,
    benchmark_2025_Return REAL,  -- Benchmark's 2025 return for beta denominator
    beta REAL,               -- ETF 2025 return / benchmark 2025 return (>= 1 to pass)
    metal_type TEXT,         -- For preciousMetals only: Gold | Silver | Platinum | Palladium
    within_metal_beta REAL,  -- Beta vs within-metal group median (PM only)
    available_on_investengine INTEGER  -- 1 = listed on InvestEngine, 0 = not
);

-- ---------------------------------------------------------------------------
-- TABLE: benchmark_etfs
-- Purpose: Pre-filter audit trail — all distributing ETFs considered for each
--          asset class BEFORE the top-N cut. Useful for reproducing screening
--          decisions and debugging beta filter thresholds.
--          Replaces benchmark_distributing_df_*.csv files.
-- Written by: database.save_benchmark_etfs(df, asset_class, portfolio_year)
-- Read by:    audit / debugging only (not used in portfolio construction)
-- ---------------------------------------------------------------------------
CREATE TABLE benchmark_etfs (
    -- Same column structure as screened_etfs; includes ETFs that failed filters
    portfolio_year  INTEGER,
    asset_class     TEXT,
    saved_at        TEXT,     -- ISO-8601 UTC timestamp

    -- All screened_etfs columns (ticker, name, beta, etc.)
    -- Full column list matches screened_etfs dynamically via pandas to_sql
    ticker TEXT,
    name   TEXT,
    beta   REAL
    -- ... remaining columns added dynamically by pandas to_sql
);

-- ---------------------------------------------------------------------------
-- TABLE: portfolios
-- Purpose: Final weighted portfolio — one row per ETF per portfolio_year.
--          Replaces final_portfolio.csv. Protected by portfolio_meta.is_locked.
-- Written by: database.save_portfolio(df, year)  [raises PortfolioLockedError if locked]
-- Read by:    notebook 04 via load_portfolio(year)
-- Locked years: 2025 (seeded from final_portfolio_25.csv, do not overwrite)
-- ---------------------------------------------------------------------------
CREATE TABLE portfolios (
    -- Inherits all screened_etfs columns plus construction weights:
    portfolio_year   INTEGER,
    created_at       TEXT,

    -- Weight columns (added by notebook 03)
    region_category_weight       REAL,  -- % allocation within asset class, by region
    intra_region_category_weight REAL,
    starting_risk_weights        REAL,  -- Pre-adjustment risk weight (%)
    normalized_risk_weights      REAL,  -- Sharpe-adjusted, re-normalised to 100%
    cash_weights                 REAL,  -- Vol-adjusted cash allocation
    final_cash_weights           REAL,  -- Final normalised cash allocation (%)
    final_risk_weights           REAL,
    investment                   REAL   -- GBP amount to invest in this position
);
