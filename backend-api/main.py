from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
import json

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
    "PDD","REGN","RIVN","ROST","SGEN","SIRI","TEAM","TTD","VRSK","VRTX","WBD",
    "WBA","WDAY","XEL","ZM","ZS"
]

HIGH_VOL_OPTIONS = [
    "SPY","QQQ","IWM","GLD","SLV","TLT","XLE","XLF","XLK","ARKK",
    "BABA","NFLX","SNAP","UBER","LYFT","COIN","HOOD","PLTR","RBLX","SOFI",
    "AMC","GME","BBBY","SPCE","MARA","RIOT","HUT","SNDL","TLRY","CGC"
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

@app.get("/")
def root():
    return {"status": "Insignia API running"}

@app.get("/earnings")
def get_earnings(universe: str = "all", weeks: int = 4):
    cache_key = f"earnings_{universe}_{weeks}"
    if is_cache_valid(cache_key):
        return cache[cache_key]["data"]

    tickers = get_universe(universe)
    today = datetime.today().date()
    end_date = today + timedelta(weeks=weeks)
    results = []

    for sym in tickers:
        try:
            tk = yf.Ticker(sym)
            cal = tk.calendar
            if cal is None:
                continue
            if isinstance(cal, dict):
                earn_date = cal.get("Earnings Date")
                if earn_date is None:
                    continue
                if isinstance(earn_date, list):
                    earn_date = earn_date[0]
                if hasattr(earn_date, "date"):
                    earn_date = earn_date.date()
                if not (today <= earn_date <= end_date):
                    continue
                results.append({
                    "ticker": sym,
                    "date": str(earn_date),
                    "time": cal.get("Earnings Time", "TBD"),
                })
        except Exception:
            continue

    results.sort(key=lambda x: x["date"])

    grouped = {}
    for r in results:
        d = r["date"]
        if d not in grouped:
            grouped[d] = []
        grouped[d].append(r)

    response = {"grouped": grouped, "total": len(results), "universe": universe}
    cache[cache_key] = {"data": response, "timestamp": datetime.now()}
    return response

@app.get("/straddle/{ticker}")
def get_straddle(ticker: str):
    return {
        "ticker": ticker,
        "message": "Live straddle data coming soon — ThetaData integration pending"
    }