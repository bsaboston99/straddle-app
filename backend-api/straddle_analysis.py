import pandas as pd
import numpy as np
from pathlib import Path
from scipy import stats

# -----------------------------
# Load all daily parquet files
# -----------------------------
def load_all_data(combined_dir: Path) -> pd.DataFrame:
    files = sorted(combined_dir.glob("*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found in {combined_dir}")
    print(f"Loading {len(files)} daily files...")
    frames = [pd.read_parquet(f) for f in files]
    df = pd.concat(frames, ignore_index=True)
    print(f"  {len(df):,} total rows loaded across {df['ticker'].nunique()} tickers.")
    return df

# -----------------------------
# Compute relative straddle ratios and earnings premium
# -----------------------------
def add_relative_straddles(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rel_straddle_a"]   = df["closestraddle_a"] / df["closespystraddle_a"]
    df["rel_straddle_b"]   = df["closestraddle_b"] / df["closespystraddle_b"]
    df["earnings_premium"] = df["rel_straddle_b"] / df["rel_straddle_a"]
    return df

# -----------------------------
# SPY DTE percentile
# -----------------------------
def get_spy_dte_percentile(
    df: pd.DataFrame,
    dte: float,
    expiration: str = "a",
    exclude_date: str = None
) -> dict:
    dte_col = f"spycalldte_{expiration}"
    spy_col = f"closespystraddle_{expiration}"

    spy_df = df[[dte_col, spy_col, "date"]].drop_duplicates(subset=["date"]).copy()
    spy_df = spy_df.dropna(subset=[dte_col, spy_col])
    bucket  = spy_df[spy_df[dte_col] == dte].copy()

    if exclude_date:
        history = bucket[bucket["date"].astype(str).str[:10] != exclude_date][spy_col].dropna()
    else:
        history = bucket[spy_col].dropna()

    if history.empty:
        return None

    current_spy = bucket.sort_values("date").iloc[-1][spy_col]
    spy_pct     = stats.percentileofscore(history, current_spy, kind="rank")
    elevation   = "HIGH" if spy_pct >= 75 else ("LOW" if spy_pct <= 25 else "NORMAL")

    return {
        "dte":                dte,
        "spy_current":        round(float(current_spy), 4),
        "spy_pct_rank":       round(float(spy_pct), 1),
        "spy_history_n":      int(len(history)),
        "spy_history_mean":   round(float(history.mean()), 4),
        "spy_history_median": round(float(history.median()), 4),
        "spy_history_pct_25": round(float(history.quantile(0.25)), 4),
        "spy_history_pct_75": round(float(history.quantile(0.75)), 4),
        "spy_elevation":      elevation,
    }

# -----------------------------
# Single metric percentile helper
# -----------------------------
def _pct_rank_series(history: pd.Series, current_val: float) -> float:
    return stats.percentileofscore(history, current_val, kind="rank")

def _signal(pct: float) -> str:
    if pct >= 75: return "RICH"
    if pct <= 25: return "CHEAP"
    return "NORMAL"

def _adj_signal(signal: str, spy_elevation: str) -> str:
    if signal == "NORMAL":
        return "NORMAL"
    direction = signal
    if (signal == "RICH"  and spy_elevation == "HIGH") or \
       (signal == "CHEAP" and spy_elevation == "LOW"):
        return f"{direction} (market-driven)"
    return f"{direction} (stock-specific)"

# -----------------------------
# Core lookup
# -----------------------------
def get_straddle_percentile(
    df: pd.DataFrame,
    ticker: str,
    dbe: int,
    exclude_date: str = None
) -> dict:
    ticker_df = df[df["ticker"] == ticker].copy()
    if ticker_df.empty:
        raise ValueError(f"Ticker '{ticker}' not found in dataset.")

    bucket = ticker_df[ticker_df["dbe"] == dbe].copy()
    if exclude_date:
        bucket = bucket[bucket["date"].astype(str).str[:10] != exclude_date]

    if bucket.empty:
        raise ValueError(
            f"No data for {ticker} at DBE={dbe}. "
            f"Available DBEs: {sorted(ticker_df['dbe'].unique().tolist())}"
        )

    hist_a   = bucket["rel_straddle_a"].dropna()
    hist_b   = bucket["rel_straddle_b"].dropna()
    hist_ep  = bucket["earnings_premium"].dropna()

    today = ticker_df[ticker_df["dbe"] == dbe].sort_values("date").iloc[-1]

    cur_a   = today["rel_straddle_a"]
    cur_b   = today["rel_straddle_b"]
    cur_ep  = today["earnings_premium"]
    cur_dte_a = today["spycalldte_a"]
    cur_dte_b = today["spycalldte_b"]

    pct_a  = _pct_rank_series(hist_a,  cur_a)
    pct_b  = _pct_rank_series(hist_b,  cur_b)
    pct_ep = _pct_rank_series(hist_ep, cur_ep)

    sig_a  = _signal(pct_a)
    sig_b  = _signal(pct_b)
    sig_ep = _signal(pct_ep)

    spy_a = get_spy_dte_percentile(df, dte=cur_dte_a, expiration="a", exclude_date=exclude_date)
    spy_b = get_spy_dte_percentile(df, dte=cur_dte_b, expiration="b", exclude_date=exclude_date)

    spy_elev_a = spy_a["spy_elevation"] if spy_a else "NORMAL"
    spy_elev_b = spy_b["spy_elevation"] if spy_b else "NORMAL"

    adj_a  = _adj_signal(sig_a,  spy_elev_a)
    adj_b  = _adj_signal(sig_b,  spy_elev_b)
    adj_ep = _adj_signal(sig_ep, spy_elev_a)

    signals = [sig_a, sig_b, sig_ep]
    cheap_count = signals.count("CHEAP")
    rich_count  = signals.count("RICH")
    if cheap_count >= 2:
        composite = f"CHEAP ({cheap_count}/3 metrics)"
    elif rich_count >= 2:
        composite = f"RICH ({rich_count}/3 metrics)"
    else:
        composite = "MIXED / NORMAL"

    def hist_stats(s):
        return {
            "n":      int(len(s)),
            "mean":   round(float(s.mean()), 4),
            "median": round(float(s.median()), 4),
            "std":    round(float(s.std()), 4),
            "pct_25": round(float(s.quantile(0.25)), 4),
            "pct_75": round(float(s.quantile(0.75)), 4),
        }

    return {
        "ticker":           ticker,
        "dbe":              dbe,
        "rel_a":            round(float(cur_a),  4),
        "pct_a":            round(float(pct_a),  1),
        "signal_a":         sig_a,
        "adj_signal_a":     adj_a,
        "hist_a":           hist_stats(hist_a),
        "rel_b":            round(float(cur_b),  4),
        "pct_b":            round(float(pct_b),  1),
        "signal_b":         sig_b,
        "adj_signal_b":     adj_b,
        "hist_b":           hist_stats(hist_b),
        "earnings_premium": round(float(cur_ep),  4),
        "pct_ep":           round(float(pct_ep),  1),
        "signal_ep":        sig_ep,
        "adj_signal_ep":    adj_ep,
        "hist_ep":          hist_stats(hist_ep),
        "composite":        composite,
        "spy_a":            spy_a,
        "spy_b":            spy_b,
        "close_a":          round(float(today["closestraddle_a"]),   4),
        "close_b":          round(float(today["closestraddle_b"]),   4),
        "spy_close_a":      round(float(today["closespystraddle_a"]), 4),
        "spy_close_b":      round(float(today["closespystraddle_b"]), 4),
    }

def get_straddle_percentile_live(
    df: pd.DataFrame,
    ticker: str,
    dbe: int,
    live_close_a: float,
    live_close_b: float,
    live_spy_close_a: float,
    live_spy_close_b: float,
    exclude_date: str = None
) -> dict:
    """
    Same as get_straddle_percentile but uses injected live values
    instead of pulling the most recent row from the parquet data.
    """
    ticker_df = df[df["ticker"] == ticker].copy()
    if ticker_df.empty:
        raise ValueError(f"Ticker '{ticker}' not found in dataset.")

    bucket = ticker_df[ticker_df["dbe"] == dbe].copy()
    if exclude_date:
        bucket = bucket[bucket["date"].astype(str).str[:10] != exclude_date]

    if bucket.empty:
        raise ValueError(
            f"No data for {ticker} at DBE={dbe}. "
            f"Available DBEs: {sorted(ticker_df['dbe'].unique().tolist())}"
        )

    # Compute live relative values
    cur_a  = live_close_a  / live_spy_close_a
    cur_b  = live_close_b  / live_spy_close_b
    cur_ep = cur_b / cur_a

    # Histories from parquet
    hist_a  = bucket["rel_straddle_a"].dropna()
    hist_b  = bucket["rel_straddle_b"].dropna()
    hist_ep = bucket["earnings_premium"].dropna()

    # Get DTE from most recent parquet row for SPY context
    recent = ticker_df[ticker_df["dbe"] == dbe].sort_values("date").iloc[-1]
    cur_dte_a = recent["spycalldte_a"]
    cur_dte_b = recent["spycalldte_b"]

    pct_a  = _pct_rank_series(hist_a,  cur_a)
    pct_b  = _pct_rank_series(hist_b,  cur_b)
    pct_ep = _pct_rank_series(hist_ep, cur_ep)

    sig_a  = _signal(pct_a)
    sig_b  = _signal(pct_b)
    sig_ep = _signal(pct_ep)

    spy_a = get_spy_dte_percentile(df, dte=cur_dte_a, expiration="a", exclude_date=exclude_date)
    spy_b = get_spy_dte_percentile(df, dte=cur_dte_b, expiration="b", exclude_date=exclude_date)

    spy_elev_a = spy_a["spy_elevation"] if spy_a else "NORMAL"
    spy_elev_b = spy_b["spy_elevation"] if spy_b else "NORMAL"

    adj_a  = _adj_signal(sig_a,  spy_elev_a)
    adj_b  = _adj_signal(sig_b,  spy_elev_b)
    adj_ep = _adj_signal(sig_ep, spy_elev_a)

    signals = [sig_a, sig_b, sig_ep]
    cheap_count = signals.count("CHEAP")
    rich_count  = signals.count("RICH")
    if cheap_count >= 2:
        composite = f"CHEAP ({cheap_count}/3 metrics)"
    elif rich_count >= 2:
        composite = f"RICH ({rich_count}/3 metrics)"
    else:
        composite = "MIXED / NORMAL"

    def hist_stats(s):
        return {
            "n":      int(len(s)),
            "mean":   round(float(s.mean()), 4),
            "median": round(float(s.median()), 4),
            "std":    round(float(s.std()), 4),
            "pct_25": round(float(s.quantile(0.25)), 4),
            "pct_75": round(float(s.quantile(0.75)), 4),
        }

    return {
        "ticker":           ticker,
        "dbe":              dbe,
        "rel_a":            round(float(cur_a),  4),
        "pct_a":            round(float(pct_a),  1),
        "signal_a":         sig_a,
        "adj_signal_a":     adj_a,
        "hist_a":           hist_stats(hist_a),
        "rel_b":            round(float(cur_b),  4),
        "pct_b":            round(float(pct_b),  1),
        "signal_b":         sig_b,
        "adj_signal_b":     adj_b,
        "hist_b":           hist_stats(hist_b),
        "earnings_premium": round(float(cur_ep),  4),
        "pct_ep":           round(float(pct_ep),  1),
        "signal_ep":        sig_ep,
        "adj_signal_ep":    adj_ep,
        "hist_ep":          hist_stats(hist_ep),
        "composite":        composite,
        "spy_a":            spy_a,
        "spy_b":            spy_b,
        "close_a":          round(live_close_a,     4),
        "close_b":          round(live_close_b,     4),
        "spy_close_a":      round(live_spy_close_a, 4),
        "spy_close_b":      round(live_spy_close_b, 4),
    }

# -----------------------------
# Batch scan
# -----------------------------
def scan_all_tickers(
    df: pd.DataFrame,
    dbe: int,
    exclude_date: str = None,
    min_history: int = 5
) -> pd.DataFrame:
    results = []
    for ticker in sorted(df["ticker"].unique()):
        try:
            r = get_straddle_percentile(df, ticker, dbe, exclude_date)
            if r["hist_a"]["n"] < min_history:
                continue
            results.append({
                "ticker":    r["ticker"],
                "composite": r["composite"],
                "pct_a":     r["pct_a"],
                "signal_a":  r["adj_signal_a"],
                "pct_b":     r["pct_b"],
                "signal_b":  r["adj_signal_b"],
                "pct_ep":    r["pct_ep"],
                "signal_ep": r["adj_signal_ep"],
                "rel_a":     r["rel_a"],
                "rel_b":     r["rel_b"],
                "ep":        r["earnings_premium"],
                "close_a":   r["close_a"],
                "spy_a_pct": r["spy_a"]["spy_pct_rank"] if r["spy_a"] else None,
                "n":         r["hist_a"]["n"],
            })
        except ValueError:
            continue

    result_df = pd.DataFrame(results)
    if result_df.empty:
        print(f"No tickers found with data at DBE={dbe}.")
        return result_df

    return result_df.sort_values(
        ["pct_ep", "pct_a"], ascending=[True, True]
    ).reset_index(drop=True)