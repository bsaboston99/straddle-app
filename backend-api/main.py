from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import requests
import pandas as pd
from datetime import datetime, timedelta

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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

def get_universe(name: str) -> list:
    if name == "sp500":
        return SP500
    elif name == "nasdaq100":
        return list(set(SP500 + NASDAQ100_EXTRA))
    elif name == "highvol":
        return HIGH_VOL_OPTIONS
    else:
        return list(set(SP500 + NASDAQ100_EXTRA + HIGH_VOL_OPTIONS))

def is_cache_valid(key: str) -> bool:
    if key not in cache:
        return False
    age = datetime.now() - cache[key]["timestamp"]
    return age < timedelta(hours=CACHE_TTL_HOURS)

def fetch_nasdaq_earnings(date_str: str) -> list:
    """
    Fetches earnings for a specific date from Nasdaq's free calendar API.
    Returns list of dicts with ticker, name, time (BMO/AMC).
    """
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={date_str}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
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
            results.append({
                "ticker": ticker,
                "name": name,
                "time": time,
                "date": date_str,
            })
        return results
    except Exception:
        return []

@app.get("/")
def root():
    return {"status": "Insignia API running"}

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
        # Skip weekends
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

@app.get("/debug/{date_str}")
def debug_nasdaq(date_str: str):
    url = f"https://api.nasdaq.com/api/calendar/earnings?date={date_str}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    }
    try:
        r = requests.get(url, headers=headers, timeout=10)
        return r.json()
    except Exception as e:
        return {"error": str(e)}
    
@app.get("/straddle/{ticker}")
def get_straddle(ticker: str):
    return {
        "ticker": ticker,
        "message": "Live straddle data coming soon — ThetaData integration pending"
    }