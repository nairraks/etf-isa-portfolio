import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from .config import DATA_CONFIG


def load_isin_ticker_map(path: Path | None = None) -> dict[str, str]:
    """Load the ISIN→ticker map shipped with the project.

    Defaults to ``data/config/isin_ticker_map.json``; callers may pass a
    custom path (e.g. for tests).
    """
    target = path or (DATA_CONFIG / "isin_ticker_map.json")
    with open(target, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_investengine_statement(
    path: str | Path,
    isin_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Parse an InvestEngine trading-statement CSV into a trades DataFrame.

    The statement has two header rows followed by eight columns:
    ``security, type, quantity, price, value, trade_datetime,
    settlement_date, broker``. Security strings include an ISIN
    (``... / ISIN IE00...``) that is mapped to our bare ticker.

    Returns a DataFrame with columns: ``ticker, trade_date, type, quantity,
    price, value, signed_qty, signed_value`` plus the raw source columns.
    Rows with unmappable ISINs or missing dates are dropped.
    """
    if isin_map is None:
        isin_map = load_isin_ticker_map()

    raw = pd.read_csv(
        path,
        skiprows=2,
        header=None,
        names=[
            "security", "type", "quantity", "price", "value",
            "trade_datetime", "settlement_date", "broker",
        ],
    )

    raw["isin"] = raw["security"].str.extract(r"ISIN\s+([A-Z]{2}[A-Z0-9]{10})")
    raw["ticker"] = raw["isin"].map(isin_map)
    raw["trade_date"] = pd.to_datetime(
        raw["trade_datetime"].str.strip(), format="%d/%m/%y %H:%M:%S"
    ).dt.normalize()

    raw["quantity"] = pd.to_numeric(raw["quantity"], errors="coerce")
    for col in ("price", "value"):
        raw[col] = (
            raw[col].astype(str)
            .str.replace("\u00a3", "", regex=False)
            .str.replace(",", "")
        )
        raw[col] = pd.to_numeric(raw[col], errors="coerce")

    trades = raw.dropna(subset=["ticker", "trade_date"]).copy()
    sign = trades["type"].str.strip().eq("Buy").map({True: 1, False: -1})
    trades["signed_qty"] = trades["quantity"] * sign
    trades["signed_value"] = trades["value"] * sign
    return trades


def combine_investengine_statements(
    *paths: str | Path,
    isin_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """Parse and combine multiple InvestEngine statement CSVs.

    Trades that appear in more than one statement (overlapping date
    ranges) are deduplicated using ``(trade_datetime, ticker, type,
    quantity)`` as the key, keeping the first occurrence.

    Parameters
    ----------
    *paths : str | Path
        One or more CSV file paths.  Non-existent paths are silently
        skipped.
    isin_map : dict, optional
        ISIN→ticker mapping; forwarded to ``parse_investengine_statement``.

    Returns
    -------
    pd.DataFrame
        Combined, deduplicated trades DataFrame sorted by trade_date.
    """
    frames = []
    for p in paths:
        p = Path(p)
        if p.exists():
            frames.append(parse_investengine_statement(p, isin_map))

    if not frames:
        return pd.DataFrame()

    combined = pd.concat(frames, ignore_index=True)
    # Deduplicate overlapping trades across statements
    combined = combined.drop_duplicates(
        subset=["trade_datetime", "ticker", "type", "quantity"],
        keep="first",
    )
    return combined.sort_values("trade_date").reset_index(drop=True)

def dynamic_portfolio_return(
    returns_df: pd.DataFrame,
    raw_weights: dict[str, float],
) -> pd.Series:
    """Compute a daily portfolio return with dynamic weight renormalisation.

    On each day only tickers with a non-NaN return contribute; their weights
    are renormalised to sum to 1 that day. Avoids the bias where
    late-listed tickers would otherwise dilute realised volatility with
    zero returns prior to their first valid data point.
    """
    tickers = [t for t in raw_weights if t in returns_df.columns]
    if not tickers:
        return pd.Series(dtype=float, index=returns_df.index)
    w = pd.Series({t: raw_weights[t] for t in tickers})
    mask = returns_df[tickers].notna()
    active_w = mask.multiply(w, axis=1)
    row_sums = active_w.sum(axis=1)
    norm_w = active_w.div(row_sums.where(row_sums > 0, np.nan), axis=0)
    return (returns_df[tickers].fillna(0) * norm_w).sum(axis=1)


def rolling_avg_pairwise_corr(
    returns_df: pd.DataFrame,
    window: int = 30,
) -> pd.Series:
    """Rolling mean of the upper-triangle (unique) pairwise correlations.

    Captures "how correlated, on average, is every asset with every other
    asset" — a blunt diversification-decay indicator that collapses to 1
    during systemic shocks.
    """
    roll_corr = returns_df.rolling(window).corr()

    def _avg(matrix: pd.DataFrame) -> float:
        if matrix.isnull().all().all():
            return float("nan")
        mask = np.triu(np.ones(matrix.shape), k=1).astype(bool)
        return float(matrix.where(mask).mean().mean())

    return roll_corr.groupby(level=0).apply(_avg)


def rolling_constituent_beta(
    returns_df: pd.DataFrame,
    port_returns: pd.Series,
    window: int = 30,
    clip: float | None = 3.0,
) -> pd.Series:
    """Mean rolling beta of each constituent vs the portfolio return series.

    For each ticker, computes Cov(r_ticker, r_port) / Var(r_port) on a
    rolling window, then averages across constituents. ``clip`` bounds each
    per-ticker beta to ±``clip`` before averaging to suppress numerical
    blowups in near-flat windows.
    """
    roll_var = port_returns.rolling(window).var()
    betas = pd.DataFrame(index=returns_df.index)
    for t in returns_df.columns:
        roll_cov = returns_df[t].rolling(window).cov(port_returns)
        beta = roll_cov / roll_var
        if clip is not None:
            beta = beta.clip(-clip, clip)
        betas[t] = beta
    return betas.mean(axis=1)


def period_metrics_table(
    ret_a: pd.Series,
    ret_b: pd.Series,
    timeline: dict[str, str],
    label_a: str = "A",
    label_b: str = "B",
) -> pd.DataFrame:
    """Period-by-period cumulative return / vol / correlation / beta.

    ``timeline`` is an ordered event→date map; consecutive pairs become
    the (start, end) of each period. For each period, computes cumulative
    return and annualised vol for both series, plus their correlation and
    the beta of B on A.
    """
    event_names = list(timeline.keys())
    event_dates = [pd.to_datetime(d) for d in timeline.values()]
    rows = []
    for i in range(len(event_names) - 1):
        s, e = event_dates[i], event_dates[i + 1]
        r_a = ret_a.loc[s:e]
        r_b = ret_b.loc[s:e]
        if len(r_a) < 2:
            continue
        cum_a = (1 + r_a).cumprod().iloc[-1] - 1
        cum_b = (1 + r_b).cumprod().iloc[-1] - 1
        vol_a = r_a.std() * np.sqrt(252)
        vol_b = r_b.std() * np.sqrt(252)
        var_a = r_a.var()
        beta = r_b.cov(r_a) / var_a if var_a > 1e-10 else np.nan
        rows.append({
            "Period": f"{event_names[i]}  \u2192  {event_names[i + 1]}",
            "Days": len(r_a),
            f"Return {label_a} (%)": cum_a * 100,
            f"Return {label_b} (%)": cum_b * 100,
            "Excess (%)": (cum_b - cum_a) * 100,
            f"Vol {label_a} (ann.)": vol_a * 100,
            f"Vol {label_b} (ann.)": vol_b * 100,
            "Correlation": r_a.corr(r_b),
            "Beta": beta,
        })
    return pd.DataFrame(rows).set_index("Period") if rows else pd.DataFrame()


class Backtester:
    def __init__(self, price_data_dict, initial_trade_date, end_date=None):
        """
        :param price_data_dict: Dictionary mapping ticker -> DataFrame with 'close' index by date.
        :param initial_trade_date: The start date of the backtest.
        :param end_date: The end date (defaults to today).
        """
        self.price_data = price_data_dict
        self.start_date = pd.Timestamp(initial_trade_date).normalize()
        self.end_date = pd.Timestamp(end_date).normalize() if end_date else pd.Timestamp.now().normalize()
        self.all_dates = pd.bdate_range(self.start_date, self.end_date)

    @classmethod
    def from_trades(cls, trades_df, provider, end_date=None):
        """Build a Backtester sized to a trades DataFrame.

        Fetches historical prices for every unique ticker in ``trades_df``
        and anchors the backtest at the first trade date.
        """
        tickers = sorted(trades_df["ticker"].dropna().unique().tolist())
        price_data = {}
        for ticker in tickers:
            try:
                price_data[ticker] = provider.get_historical_prices(ticker)
            except Exception as exc:
                print(f"  Warning: could not fetch data for {ticker}: {exc}")
        first_trade = pd.Timestamp(trades_df["trade_date"].min()).normalize()
        return cls(price_data, first_trade, end_date)

    @property
    def price_df(self):
        """
        Returns a single combined DataFrame of 'close' prices for all tickers.
        Index = date, Columns = tickers.
        """
        if not hasattr(self, "_price_df_cache"):
            series_dict = {ticker: df["close"] for ticker, df in self.price_data.items() if "close" in df.columns}
            self._price_df_cache = pd.DataFrame(series_dict)
        return self._price_df_cache

    def get_price(self, ticker, date):
        if ticker not in self.price_data:
            return None
        df = self.price_data[ticker]
        match = df[df.index <= date]
        if match.empty:
            return None
        return float(match["close"].iloc[-1])

    def compute_portfolio_value(self, shares_dict, date):
        val = 0
        for ticker, qty in shares_dict.items():
            px = self.get_price(ticker, date)
            if px:
                val += qty * px
        return val

    def run_twr_series(self, trades_df):
        """
        Computes a daily TWR series from a dataframe of trades.
        Chains sub-period returns at every date where a trade occurs.
        """
        trades = trades_df.copy()
        trades["trade_date"] = pd.to_datetime(trades["trade_date"]).dt.normalize()
        rebalance_dates = sorted(trades["trade_date"].unique())
        
        # Ensure we start at the first trade date
        first_date = min(rebalance_dates[0], self.start_date)
        period_boundaries = sorted(set([first_date] + [d for d in rebalance_dates if d > first_date] + [self.end_date]))
        
        cumulative_factor = 1.0
        daily_returns = {} # date -> cumulative % gain
        
        running_shares = defaultdict(float)
        
        # We'll build the daily series by tracking the current sub-period's "start value"
        # and multiplying by the "intra-period growth".
        
        # Pre-calculate sub-period benchmarks
        sub_periods = []
        for i in range(len(period_boundaries) - 1):
            p_start, p_end = period_boundaries[i], period_boundaries[i+1]
            
            # Apply trades happening at p_start
            start_trades = trades[trades["trade_date"] == p_start]
            for _, t in start_trades.iterrows():
                running_shares[t["ticker"]] += t["signed_qty"]
            
            # Record state for this sub-period
            sub_periods.append({
                "start": p_start,
                "end": p_end,
                "shares": dict(running_shares),
                "val_at_start": self.compute_portfolio_value(running_shares, p_start)
            })

        current_sp_idx = 0
        current_cum_factor = 1.0
        
        for d in self.all_dates:
            # Move to next sub-period if date d has passed the boundary
            while current_sp_idx < len(sub_periods) - 1 and d >= sub_periods[current_sp_idx + 1]["start"]:
                sp = sub_periods[current_sp_idx]
                next_sp_start = sub_periods[current_sp_idx + 1]["start"]
                # Value at the end of the finished sub-period (pre-trades of next period)
                val_end_pre = self.compute_portfolio_value(sp["shares"], next_sp_start)
                if sp["val_at_start"] > 0:
                    current_cum_factor *= (val_end_pre / sp["val_at_start"])
                current_sp_idx += 1
            
            # Calculate return for current day within current sub-period
            sp = sub_periods[current_sp_idx]
            val_start = sp["val_at_start"]
            val_now = self.compute_portfolio_value(sp["shares"], d)
            
            if val_start > 0:
                intra_growth = val_now / val_start
                daily_returns[d] = (current_cum_factor * intra_growth - 1) * 100
            else:
                daily_returns[d] = 0.0
                
        return pd.Series(daily_returns)

    def run_buy_and_hold_series(self, initial_shares):
        """
        Computes a daily return series for a fixed set of shares.
        Uses adjusted prices to capture dividends.
        """
        val_start = self.compute_portfolio_value(initial_shares, self.start_date)
        daily_returns = {}
        for d in self.all_dates:
            val_now = self.compute_portfolio_value(initial_shares, d)
            daily_returns[d] = (val_now / val_start - 1) * 100 if val_start > 0 else 0
        return pd.Series(daily_returns)

    def build_blended_benchmark_no_rebalance(self, weights):
        """
        Build a fixed-weight blended benchmark as a true *buy-and-forget* basket.

        Each ticker is "bought" at its first observed price with the given
        weight and held without rebalancing. Weights therefore drift as the
        component prices diverge — the natural behaviour of an untouched
        basket. Mathematically::

            V(t) / V(0) = Σ w_i · ( P_i(t) / P_i(0) )

        This is the right counterfactual for "what if I had bought this
        blended basket on day 0 and never touched it again?" — the standard
        comparator for an actual TWR series that *does* get rebalanced.

        TER drag is **deliberately not applied here**. Component price series
        come from ETF adjusted-close data (AlphaVantage / yfinance), which
        already embeds the fund's TER inside its NAV — applying a manual
        ``ter / 252`` daily drag on top would double-count costs. See the
        "TER, OCF and adjusted-close prices" section of the methodology page
        for the full rationale; the proper next-step metric is **tracking
        difference vs index**, listed under Future Work.

        :param weights: dict mapping ticker -> weight (not required to sum
                        to 1; normalised internally).
        :return: pandas Series indexed by ``self.all_dates``, expressed as
                 cumulative % gain (e.g. 5.0 = +5%) relative to the start.
        """
        df = self.price_df
        if df is None or df.empty:
            return pd.Series(dtype=float)

        available = [t for t in weights if t in df.columns and weights[t] > 0]
        if not available:
            return pd.Series(dtype=float)

        total_w = sum(weights[t] for t in available)
        if total_w <= 0:
            return pd.Series(dtype=float)
        norm_w = {t: weights[t] / total_w for t in available}

        # Forward- then backward-fill so every ticker has a reference P(0)
        # even if its listing history is shorter than the backtest window.
        prices = df[available].reindex(self.all_dates).ffill().bfill()
        p0 = prices.iloc[0]
        if p0.isna().any() or (p0 <= 0).any():
            return pd.Series(dtype=float)

        # Weighted sum of per-ticker growth factors — the buy-and-hold basket.
        growth = prices.divide(p0)
        portfolio_growth = sum(growth[t] * norm_w[t] for t in available)
        return (portfolio_growth - 1.0) * 100.0

    def build_blended_benchmark_rebalanced(self, weights):
        """
        Build a fixed-weight blended benchmark that is **rebalanced daily**
        back to the target weights.

        Applies the target weights to each day's component returns and
        compounds the resulting portfolio daily return::

            r_p(t) = Σ w_i · r_i(t)
            V(t)   = Π ( 1 + r_p(t') )    for t' ≤ t

        This is *not* a buy-and-forget basket — holding fixed weights each
        day is mathematically equivalent to end-of-day rebalancing. It is
        a common index-provider convention (many published "60/40" style
        indices work this way) and remains useful as a separate comparator,
        but it will differ from ``build_blended_benchmark_no_rebalance``
        by the "volatility drag" / "rebalancing bonus" whose sign depends
        on the components' co-movement.

        TER drag is deliberately not applied (see the no-rebalance variant's
        docstring for the full rationale).

        :param weights: dict mapping ticker -> weight (not required to sum
                        to 1; normalised internally).
        :return: pandas Series indexed by ``self.all_dates``, expressed as
                 cumulative % gain (e.g. 5.0 = +5%) relative to the start.
        """
        df = self.price_df
        if df is None or df.empty:
            return pd.Series(dtype=float)

        available = [t for t in weights if t in df.columns and weights[t] > 0]
        if not available:
            return pd.Series(dtype=float)

        total_w = sum(weights[t] for t in available)
        if total_w <= 0:
            return pd.Series(dtype=float)
        norm_w = {t: weights[t] / total_w for t in available}

        prices = df[available].reindex(self.all_dates).ffill()
        daily_returns = prices.pct_change().fillna(0.0)

        port_daily = sum(daily_returns[t] * norm_w[t] for t in available)
        cumulative = (1.0 + port_daily).cumprod() - 1.0
        return cumulative * 100.0

    def run_simulated_rebalance(self, initial_shares, target_weights, rebalance_dates):
        """
        Simulates a rebalancing strategy at specific dates.
        Rebalances back to target weights on every date in rebalance_dates.
        """
        current_shares = dict(initial_shares)
        cumulative_factor = 1.0
        daily_returns = {}
        
        # Sort and ensure unique
        rebals = sorted(set(rebalance_dates))
        if self.start_date not in rebals:
            rebals = [self.start_date] + rebals
            
        sub_periods = []
        for i in range(len(rebals)):
            p_start = rebals[i]
            p_end = rebals[i+1] if i + 1 < len(rebals) else self.end_date + pd.Timedelta(days=1)
            
            # Value at start (already rebalanced at end of prev period, except first)
            val_start = self.compute_portfolio_value(current_shares, p_start)
            
            sub_periods.append({
                "start": p_start,
                "end": p_end,
                "shares": dict(current_shares),
                "val_at_start": val_start
            })
            
            # Calculate shares for NEXT period if needed
            if i + 1 < len(rebals):
                # Value at end of current period
                next_rebal_date = rebals[i+1]
                val_pre = self.compute_portfolio_value(current_shares, next_rebal_date)
                # Perfect rebalance back to target weights
                current_shares = {}
                for ticker, weight in target_weights.items():
                    px = self.get_price(ticker, next_rebal_date)
                    if px and px > 0:
                        current_shares[ticker] = (val_pre * weight) / px
                    else:
                        current_shares[ticker] = 0

        # Now fill daily series
        current_sp_idx = 0
        current_cum_factor = 1.0
        
        for d in self.all_dates:
            while current_sp_idx < len(sub_periods) - 1 and d >= sub_periods[current_sp_idx + 1]["start"]:
                sp = sub_periods[current_sp_idx]
                next_sp_start = sub_periods[current_sp_idx + 1]["start"]
                val_end_pre = self.compute_portfolio_value(sp["shares"], next_sp_start)
                if sp["val_at_start"] > 0:
                    current_cum_factor *= (val_end_pre / sp["val_at_start"])
                current_sp_idx += 1
            
            sp = sub_periods[current_sp_idx]
            val_start = sp["val_at_start"]
            val_now = self.compute_portfolio_value(sp["shares"], d)
            
            if val_start > 0:
                intra_growth = val_now / val_start
                daily_returns[d] = (current_cum_factor * intra_growth - 1) * 100
            else:
                daily_returns[d] = 0.0
                
        return pd.Series(daily_returns)
