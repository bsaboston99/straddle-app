from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
import os
from datetime import datetime, timedelta
from pathlib import Path
from straddle_analysis import load_all_data, add_relative_straddles, get_straddle_percentile, get_straddle_percentile_live

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Local override via env var; defaults to data/combined_daily relative to this file
COMBINED_DIR = Path(os.environ.get(
    "COMBINED_DIR",
    Path(__file__).parent / "data" / "combined_daily"
))

MOCK_LIVE = {
    "NVDA": {"close_a": 0.0522, "close_b": 0.0669, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "ORCL": {"close_a": 0.0666, "close_b": 0.0829, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "ADBE": {"close_a": 0.0561, "close_b": 0.0698, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "TSLA": {"close_a": 0.1028, "close_b": 0.1289, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "AMZN": {"close_a": 0.0675, "close_b": 0.0852, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "META": {"close_a": 0.0592, "close_b": 0.0738, "spy_close_a": 0.0078, "spy_close_b": 0.0151},
    "SPY":  {"close_a": 0.0208, "close_b": 0.0271, "spy_close_a": 0.0208, "spy_close_b": 0.0271},
}

df_global = None

@app.on_event("startup")
async def startup_event():
    global df_global
    print("Loading parquet files...")
    try:
        df_global = load_all_data(COMBINED_DIR)
        df_global = add_relative_straddles(df_global)
        print(f"Parquet files loaded successfully. {len(df_global):,} rows.")
    except Exception as e:
        print(f"WARNING: Could not load parquet files: {e}")
        df_global = None

SP500 = [
    "AAPL","MSFT","NVDA","AMZN","META","GOOGL","TSLA","BRK-B","JPM","UNH",
    "XOM","LLY","JNJ","V","PG","MA","HD","CVX","MRK","ABBV","PEP","COST",
    "ADBE","CRM","TMO","BAC","ACN","MCD","QCOM","NKE","TXN","AMD","PM","DHR",
    "ORCL","WMT","AVGO","CAT","GS","RTX","HON","AMGN","LMT","SBUX","GILD",
    "MDLZ","AXP","ISRG","BKNG","NOW","PANW","LRCX","ADI","KLAC","SNPS","CDNS"
]

NASDAQ100_EXTRA = [
    "ASML","MELI","ABNB","CRWD","DXCM","FANG","FTNT","IDXX","ILMN","KDP",
    "LCID","LULU","MAR","MRNA","MTCH","MU","NFLX","ODFL","ON","PAYX","PCAR",
    "PDD","REGN","RIVN","ROST","TEAM","TTD","VRSK","VRTX","WDAY","ZM","ZS"
]

HIGH_VOL_OPTIONS = [
    "SPY","QQQ","IWM","GLD","SLV","TLT","XLE","XLF","XLK","ARKK",
    "BABA","NFLX","SNAP","UBER","LYFT","COIN","HOOD","PLTR","RBLX","SOFI",
    "AMC","GME","MARA","RIOT","SNDL","TLRY","CGC"
]

cache = {}
CACHE_TTL_HOURS = 6

def is_cache_valid(key: str) -> bool:
    if key not in cache:
        return False
    age = datetime.now() - cache[key]["timestamp"]
    return age < timedelta(hours=CACHE_TTL_HOURS)

def get_universe(name: str) -> list:
    if name == "sp500":
        return SP500
    elif name == "nasdaq100":
        return list(set(SP500 + NASDAQ100_EXTRA))
    elif name == "highvol":
        return HIGH_VOL_OPTIONS
    else:
        return list(set(SP500 + NASDAQ100_EXTRA + HIGH_VOL_OPTIONS))

def fetch_nasdaq_earnings(date_str: str) -> list:
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={date_str}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        rows = data.get("data", {}).get("rows", []) or []
        results = []
        for row in rows:
            ticker = row.get("symbol", "").strip()
            name = row.get("name", "").strip()
            time_raw = row.get("time", "").strip()
            if not ticker:
                continue
            if "pre-market" in time_raw.lower():
                time = "BMO"
            elif "after-hours" in time_raw.lower():
                time = "AMC"
            else:
                time = "TBD"
            results.append({"ticker": ticker, "name": name, "time": time, "date": date_str})
        return results
    except Exception:
        return []

@app.get("/")
def root():
    return {
        "status": "Insignia API running",
        "parquet_loaded": df_global is not None,
        "rows": len(df_global) if df_global is not None else 0
    }

@app.get("/earnings")
def get_earnings(universe: str = "all", weeks: int = 4):
    cache_key = f"earnings_{universe}_{weeks}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    universe_tickers = set(get_universe(universe))
    today = datetime.today().date()
    grouped = {}
    total = 0

    for i in range(weeks * 7):
        date = today + timedelta(days=i)
        if date.weekday() >= 5:
            continue
        date_str = str(date)
        rows = fetch_nasdaq_earnings(date_str)
        filtered = [r for r in rows if r["ticker"] in universe_tickers]
        if filtered:
            grouped[date_str] = filtered
            total += len(filtered)

    response = {"grouped": grouped, "total": total, "universe": universe}
    cache[cache_key] = {"data": response, "timestamp": datetime.now()}
    return response

@app.get("/straddle/{ticker}")
def get_straddle(ticker: str, dbe: int = 0):
    if df_global is None:
        raise HTTPException(status_code=503, detail="Parquet data not loaded.")

    cache_key = f"straddle_{ticker.upper()}_{dbe}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    sym = ticker.upper()

    try:
        if sym in MOCK_LIVE:
            live = MOCK_LIVE[sym]
            result = get_straddle_percentile_live(
                df_global,
                ticker=sym,
                dbe=dbe,
                live_close_a=live["close_a"],
                live_close_b=live["close_b"],
                live_spy_close_a=live["spy_close_a"],
                live_spy_close_b=live["spy_close_b"],
            )
        else:
            result = get_straddle_percentile(df_global, ticker=sym, dbe=dbe)

        response = {
            "ticker":           result["ticker"],
            "dbe":              result["dbe"],
            "pct_a":            result["pct_a"],
            "signal_a":         result["signal_a"],
            "adj_signal_a":     result["adj_signal_a"],
            "pct_b":            result["pct_b"],
            "signal_b":         result["signal_b"],
            "adj_signal_b":     result["adj_signal_b"],
            "pct_ep":           result["pct_ep"],
            "signal_ep":        result["signal_ep"],
            "adj_signal_ep":    result["adj_signal_ep"],
            "composite":        result["composite"],
            "rel_a":            result["rel_a"],
            "rel_b":            result["rel_b"],
            "earnings_premium": result["earnings_premium"],
            "close_a":          result["close_a"],
            "close_b":          result["close_b"],
            "spy_close_a":      result["spy_close_a"],
            "spy_close_b":      result["spy_close_b"],
            "hist_a":           result["hist_a"],
            "hist_b":           result["hist_b"],
            "hist_ep":          result["hist_ep"],
            "spy_a":            result["spy_a"],
            "spy_b":            result["spy_b"],
        }

        cache[cache_key] = {"data": response, "timestamp": datetime.now()}
        return response

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/history/{ticker}")
def get_history(ticker: str, dbe: int = 0):
    if df_global is None:
        raise HTTPException(status_code=503, detail="Parquet data not loaded.")

    cache_key = f"history_{ticker.upper()}_{dbe}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    sym = ticker.upper()

    ticker_all = df_global[df_global["ticker"] == sym].sort_values("date")

    dbe0 = ticker_all[ticker_all["dbe"] == 0][
        ["date", "er_date", "closestraddle_a", "closestraddle_b",
         "closespystraddle_a", "closespystraddle_b", "stock_close"]
    ].dropna(subset=["closestraddle_a"]).sort_values("date")

    if dbe0.empty:
        raise HTTPException(status_code=404, detail=f"No history for {sym} at DBE=0")

    date_map = {}
    for _, row in ticker_all.iterrows():
        key = str(row["date"])[:10]
        date_map[key] = row

    rows = []
    for _, row in dbe0.iterrows():
        dbe0_date = pd.Timestamp(row["date"])
        er_date_str = str(row["er_date"])[:10]
        stock_close = round(float(row["stock_close"]), 4) if pd.notna(row["stock_close"]) else None

        # Find next trading day
        next_date = dbe0_date + pd.Timedelta(days=1)
        post = None
        for _ in range(7):
            next_key = str(next_date)[:10]
            if next_key in date_map:
                next_row = date_map[next_key]
                post_open  = float(next_row["stock_open"])  if pd.notna(next_row["stock_open"])  else None
                post_close = float(next_row["stock_close"]) if pd.notna(next_row["stock_close"]) else None
                post_straddle_a = round(float(next_row["closestraddle_a"]), 4) if pd.notna(next_row["closestraddle_a"]) else None
                post_straddle_b = round(float(next_row["closestraddle_b"]), 4) if pd.notna(next_row["closestraddle_b"]) else None

                open_chg_pct  = round((post_open  - stock_close) / stock_close * 100, 2) if stock_close and post_open  else None
                close_chg_pct = round((post_close - stock_close) / stock_close * 100, 2) if stock_close and post_close else None

                post = {
                    "stock_open":       round(post_open,  4) if post_open  else None,
                    "stock_close":      round(post_close, 4) if post_close else None,
                    "open_chg_pct":     open_chg_pct,
                    "close_chg_pct":    close_chg_pct,
                    "closestraddle_a":  post_straddle_a,
                    "closestraddle_b":  post_straddle_b,
                }
                break
            next_date += pd.Timedelta(days=1)

        rows.append({
            "date":               str(row["date"])[:10],
            "er_date":            er_date_str,
            "closestraddle_a":    round(float(row["closestraddle_a"]), 4),
            "closestraddle_b":    round(float(row["closestraddle_b"]), 4),
            "closespystraddle_a": round(float(row["closespystraddle_a"]), 4),
            "closespystraddle_b": round(float(row["closespystraddle_b"]), 4),
            "stock_close":        stock_close,
            "post_stock_open":    post["stock_open"]      if post else None,
            "post_stock_close":   post["stock_close"]     if post else None,
            "open_chg_pct":       post["open_chg_pct"]   if post else None,
            "close_chg_pct":      post["close_chg_pct"]  if post else None,
            "post_closestraddle_a": post["closestraddle_a"] if post else None,
            "post_closestraddle_b": post["closestraddle_b"] if post else None,
        })

    response = {"ticker": sym, "dbe": 0, "data": rows}
    cache[cache_key] = {"data": response, "timestamp": datetime.now()}
    return response

@app.get("/scan")
def get_scan(dbe: int = 0):
    if df_global is None:
        raise HTTPException(status_code=503, detail="Parquet data not loaded.")

    cache_key = f"scan_{dbe}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    results = {}
    for ticker in sorted(df_global["ticker"].unique()):
        try:
            r = get_straddle_percentile(df_global, ticker=ticker, dbe=dbe)
            if r["hist_a"]["n"] < 3:
                continue
            results[ticker] = {
                "pct_a":            r["pct_a"],
                "pct_b":            r["pct_b"],
                "pct_ep":           r["pct_ep"],
                "signal_a":         r["signal_a"],
                "signal_b":         r["signal_b"],
                "signal_ep":        r["signal_ep"],
                "adj_signal_a":     r["adj_signal_a"],
                "adj_signal_b":     r["adj_signal_b"],
                "adj_signal_ep":    r["adj_signal_ep"],
                "composite":        r["composite"],
                "close_a":          r["close_a"],
                "close_b":          r["close_b"],
                "earnings_premium": r["earnings_premium"],
                "rel_a":            r["rel_a"],
                "rel_b":            r["rel_b"],
            }
        except Exception:
            continue

    response = {"data": results, "dbe": dbe, "count": len(results)}
    cache[cache_key] = {"data": response, "timestamp": datetime.now()}
    return response


@app.get("/analysis")
def get_analysis(dbe: int = 0):
    if df_global is None:
        raise HTTPException(status_code=503, detail="Parquet data not loaded.")

    cache_key = f"analysis_{dbe}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    results = []
    for ticker in sorted(df_global["ticker"].unique()):
        ticker_df = df_global[df_global["ticker"] == ticker]
        bucket = (
            ticker_df[ticker_df["dbe"] == dbe]
            .dropna(subset=["closestraddle_a"])
            .sort_values("date")
        )
        if len(bucket) < 3:
            continue

        vals = bucket["closestraddle_a"]

        results.append({
            "ticker":   ticker,
            "n":        int(len(vals)),
            "mean_a":   round(float(vals.mean()),         4),
            "std_a":    round(float(vals.std()),          4),
            "median_a": round(float(vals.median()),       4),
            "pct_25_a": round(float(vals.quantile(0.25)), 4),
            "pct_75_a": round(float(vals.quantile(0.75)), 4),
        })

    response = {"tickers": results, "dbe": dbe, "count": len(results)}
    cache[cache_key] = {"data": response, "timestamp": datetime.now()}
    return response


@app.get("/debug/{date_str}")
def debug_nasdaq(date_str: str):
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={date_str}"
    headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}