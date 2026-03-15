"""Shared utilities for the ETF ISA portfolio notebooks."""

from .config import (
    ALPHAVANTAGE_API_KEY,
    DATA_CONFIG,
    DATA_INTERMEDIATE,
    DATA_OUTPUT,
    DATA_PROVIDER,
    DATA_RAW,
    DB_PATH,
    PROJECT_ROOT,
)
from .data_io import (
    PortfolioLockedError,
    get_asset_class_from_filename,
    get_region_category_from_filename,
    load_config,
    load_intermediate,
    load_output,
    load_raw_etf_data,
    save_intermediate,
    save_output,
)
from .data_provider import DataProvider
from .database import (
    init_db,
    list_portfolio_versions,
    load_portfolio,
    load_raw_etf_data as load_raw_from_db,
    load_screened_etfs,
    lock_portfolio,
    save_portfolio,
    save_raw_etf_data,
    save_screened_etfs,
    seed_2025_portfolio,
)
from .metrics import (
    calculate_annualized_volatility,
    calculate_daily_pnl,
    calculate_period_metrics,
    calculate_sharpe_ratio,
    interpolate_adjustment_factor,
)
from .platform_check import check_etf_availability

__all__ = [
    # config
    "PROJECT_ROOT",
    "DATA_RAW",
    "DATA_INTERMEDIATE",
    "DATA_OUTPUT",
    "DATA_CONFIG",
    "DATA_PROVIDER",
    "ALPHAVANTAGE_API_KEY",
    "DB_PATH",
    # data_provider
    "DataProvider",
    # data_io
    "load_raw_etf_data",
    "save_intermediate",
    "load_intermediate",
    "save_output",
    "load_output",
    "load_config",
    "get_region_category_from_filename",
    "get_asset_class_from_filename",
    "PortfolioLockedError",
    # database
    "init_db",
    "save_raw_etf_data",
    "load_raw_from_db",
    "save_screened_etfs",
    "load_screened_etfs",
    "save_portfolio",
    "load_portfolio",
    "lock_portfolio",
    "list_portfolio_versions",
    "seed_2025_portfolio",
    # metrics
    "calculate_annualized_volatility",
    "calculate_sharpe_ratio",
    "interpolate_adjustment_factor",
    "calculate_period_metrics",
    "calculate_daily_pnl",
    # platform_check
    "check_etf_availability",
]
