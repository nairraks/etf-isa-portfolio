import pandas as pd
import numpy as np
from collections import defaultdict

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

    def build_blended_benchmark(self, weights, ter_bps=None):
        """
        Build a fixed-weight blended benchmark series as a cumulative % gain.

        Uses the cached ``price_df`` to compound daily returns for each component,
        then combines them as a weighted average of cumulative growth factors.
        This represents a "buy and forget" basket that does NOT rebalance — a
        clean counterfactual for the actual portfolio.

        :param weights: dict mapping ticker -> weight (not required to sum to 1;
                        normalised internally).
        :param ter_bps: optional dict mapping ticker -> annual TER in basis points
                        (e.g. 19 for a 0.19% TER). When provided, a daily drag of
                        ``ter_bps / 1e4 / 252`` is subtracted from each component's
                        daily return before compounding.
        :return: pandas Series indexed by self.all_dates, expressed as cumulative
                 % gain (e.g. 5.0 = +5%) relative to the start date.
        """
        df = self.price_df
        if df is None or df.empty:
            return pd.Series(dtype=float)

        # Restrict to tickers with price history and non-zero weight
        available = [t for t in weights if t in df.columns and weights[t] > 0]
        if not available:
            return pd.Series(dtype=float)

        # Normalise weights across available tickers
        total_w = sum(weights[t] for t in available)
        if total_w <= 0:
            return pd.Series(dtype=float)
        norm_w = {t: weights[t] / total_w for t in available}

        # Align to backtest dates and forward-fill gaps
        prices = df[available].reindex(self.all_dates).ffill()
        daily_returns = prices.pct_change().fillna(0.0)

        # Apply TER drag per component, if provided.
        # Daily drag = (annual_ter_fraction) / 252.
        if ter_bps:
            for t in available:
                t_bps = ter_bps.get(t, 0) or 0
                if t_bps:
                    daily_returns[t] = daily_returns[t] - (t_bps / 1e4) / 252.0

        # Weighted portfolio daily return, then compound to a cumulative % gain.
        port_daily = sum(daily_returns[t] * norm_w[t] for t in available)
        cumulative = (1.0 + port_daily).cumprod() - 1.0
        return cumulative * 100.0

    @staticmethod
    def apply_ter_drag(cumulative_return_series, ter_bps):
        """
        Subtract a daily TER accrual from an existing cumulative-% return series.

        The input series is interpreted as cumulative % gain (e.g. 5.0 = +5%)
        at each date in its index, consistent with the output of
        :meth:`run_twr_series`, :meth:`run_buy_and_hold_series`, and
        :meth:`build_blended_benchmark`.

        Daily TER drag = ``ter_bps / 1e4 / 252``. The drag accumulates over
        trading days between consecutive index entries (typically 1 per entry).

        :param cumulative_return_series: pandas Series of cumulative % returns.
        :param ter_bps: annual TER in basis points (e.g. 19 for 0.19%). A value
                        of 0 is a no-op and returns a copy of the input.
        :return: pandas Series of net-of-TER cumulative % returns, same index.
        """
        s = pd.Series(cumulative_return_series).copy()
        if s.empty or not ter_bps:
            return s

        # Convert % series to growth factor, then strip TER each trading day.
        factors = 1.0 + s / 100.0
        daily_drag = (ter_bps / 1e4) / 252.0
        # Assume one trading day per index step after the first.
        steps = np.arange(len(s), dtype=float)
        drag_factors = (1.0 - daily_drag) ** steps
        net_factors = factors * drag_factors
        return (net_factors - 1.0) * 100.0

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
