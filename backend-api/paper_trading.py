"""
Paper trading engine for the earnings-straddle strategy.

Scope and honesty check up front: the ledger, rule logic, and position sizing
here follow exactly what was calibrated and agreed on earlier (entry when
dbe is 2 or 3 and the model's predicted_log_ratio >= 0.3, 10% of current
equity per trade, no hard concurrency cap -- just skip a signal if there
isn't enough buying power). That part is solid.

Exit is now two-layered. The model's predicted_log_ratio at entry sets a
concrete target_rel_straddle_a (entry_rel_straddle_a * exp(predicted_log_ratio)),
and every day the position is open before dbe==0, a fresh rel_straddle_a is
computed for the held contracts and compared against that target -- hit it,
and the position sells immediately instead of waiting. dbe==0 remains a hard
backstop exit regardless of the target, since holding through the actual
earnings print was never part of this strategy.

CAVEAT worth being honest about: the model was trained to predict
rel_straddle_a movement between historical (entry_dbe, exit_dbe) pairs, not
to predict a day-by-day path or a reliable "peak" level. Selling the moment
the predicted ratio is reached is a reasonable, literal reading of "let the
model decide," but that exact rule hasn't been backtested on its own the way
the entry threshold was -- worth watching the first several trades closely
before trusting it as much as the entry side.

The Alpaca option-contract-lookup and multi-leg order submission calls below
are written against alpaca-py's documented API shape, but have NOT been run
against a live account -- there were no credentials available to test with.
Treat those specific calls (find_atm_contract, place_straddle_entry,
close_straddle) as a first draft: run _claude_alpaca_connection_test.py
first, then dry-run run_daily_check() against a quiet day before trusting it
with real (paper) order flow, and expect to adjust call shapes if alpaca-py
has moved since this was written.

Storage: SQLite via stdlib sqlite3, in a single file (paper_trading.db).
Locally this just lands in ./data/. In production, DB_PATH is driven by the
PAPER_TRADING_DB env var (see render.yaml), which points at a Render
persistent disk mounted on insignia-api -- so a redeploy or restart no
longer wipes the ledger the way it would on the service's own ephemeral
filesystem. If this ever needs to scale past a single instance (persistent
disks don't support that), migrating to a real Postgres connection is the
next step; the schema is simple enough that porting it later isn't a rewrite.
"""
import os
import sqlite3
import json
from datetime import datetime, date, timedelta
from pathlib import Path
from contextlib import contextmanager

from dotenv import load_dotenv
load_dotenv()  # loads backend-api/.env into the process environment -- this
                # needs to happen HERE (not just in standalone test scripts)
                # so it's picked up no matter what imports this module,
                # including uvicorn running main.py.

import joblib
import numpy as np
import pandas as pd

import notifications

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ENTRY_DBE_MIN, ENTRY_DBE_MAX = 2, 3
THRESHOLD = 0.3
POSITION_FRACTION = 0.10  # 10% of current equity per trade

DB_PATH = Path(os.environ.get("PAPER_TRADING_DB", Path(__file__).parent / "data" / "paper_trading.db"))
MODEL_PATH = Path(os.environ.get("MODEL_PATH", Path(__file__).parent / "model" / "straddle_model_v2.joblib"))

ALPACA_API_KEY = os.environ.get("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.environ.get("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.environ.get("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

if "paper-api" not in ALPACA_BASE_URL:
    raise RuntimeError(
        f"ALPACA_BASE_URL='{ALPACA_BASE_URL}' does not look like the paper "
        "trading endpoint. Refusing to start -- this module is paper-trading "
        "only. If you've deliberately moved to live trading, that decision "
        "needs to be made explicitly elsewhere, not silently allowed here."
    )

_model_bundle = None
_trading_client = None
_option_data_client = None


def get_model():
    global _model_bundle
    if _model_bundle is None:
        if not MODEL_PATH.exists():
            raise RuntimeError(
                f"Model file not found at {MODEL_PATH}. Run _claude_ml_v2_persist.py "
                "and copy straddle_model_v2.joblib + straddle_model_v2_metadata.json here."
            )
        _model_bundle = joblib.load(MODEL_PATH)
    return _model_bundle["model"], _model_bundle["feature_names"]


def get_trading_client():
    global _trading_client
    if _trading_client is None:
        from alpaca.trading.client import TradingClient
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            raise RuntimeError("ALPACA_API_KEY / ALPACA_SECRET_KEY not set.")
        _trading_client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=True)
    return _trading_client


def get_option_data_client():
    global _option_data_client
    if _option_data_client is None:
        from alpaca.data.historical.option import OptionHistoricalDataClient
        _option_data_client = OptionHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
    return _option_data_client


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

@contextmanager
def get_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                er_date TEXT NOT NULL,
                checked_at TEXT NOT NULL,
                dbe INTEGER,
                predicted_log_ratio REAL,
                decision TEXT NOT NULL,       -- "entered" | "skipped_threshold" | "skipped_no_cash" | "skipped_dbe" | "error"
                detail TEXT,
                UNIQUE(ticker, er_date, checked_at)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticker TEXT NOT NULL,
                er_date TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                exit_date TEXT,
                call_symbol TEXT NOT NULL,
                put_symbol TEXT NOT NULL,
                predicted_log_ratio REAL,
                position_size_usd REAL,
                entry_cost REAL,
                exit_value REAL,
                pnl_usd REAL,
                pnl_pct REAL,
                status TEXT NOT NULL DEFAULT 'open',   -- "open" | "closed" | "expired_unfilled" | "error"
                alpaca_entry_order_id TEXT,
                alpaca_exit_order_id TEXT,
                entry_rel_straddle_a REAL,
                target_rel_straddle_a REAL,
                qty INTEGER,
                notes TEXT,
                UNIQUE(ticker, er_date)
            )
        """)
        # Migration for a trades table that already existed before the
        # target-exit columns above were added -- CREATE TABLE IF NOT EXISTS
        # is a no-op on an existing table, so an older db file needs these
        # added explicitly. Safe to run every startup: ADD COLUMN on a
        # column that already exists just raises, which is ignored.
        for col, coltype in [
            ("entry_rel_straddle_a", "REAL"),
            ("target_rel_straddle_a", "REAL"),
            ("qty", "INTEGER"),
            ("entry_time", "TEXT"),  # full timestamp; entry_date above is date-only
        ]:
            try:
                conn.execute(f"ALTER TABLE trades ADD COLUMN {col} {coltype}")
            except sqlite3.OperationalError:
                pass
        conn.commit()


def log_signal(ticker, er_date, dbe, predicted_log_ratio, decision, detail=""):
    with get_db() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO signals (ticker, er_date, checked_at, dbe, predicted_log_ratio, decision, detail) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (ticker, er_date, datetime.utcnow().isoformat(), dbe, predicted_log_ratio, decision, detail),
        )


def get_open_trade(ticker, er_date):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM trades WHERE ticker = ? AND er_date = ? AND status = 'open'",
            (ticker, er_date),
        ).fetchone()
        return dict(row) if row else None


def record_trade_entry(ticker, er_date, call_symbol, put_symbol, predicted_log_ratio,
                        position_size_usd, entry_cost, order_id, entry_rel_straddle_a=None,
                        target_rel_straddle_a=None, qty=1, notes=""):
    with get_db() as conn:
        now = datetime.now()
        conn.execute(
            "INSERT INTO trades (ticker, er_date, entry_date, entry_time, call_symbol, put_symbol, "
            "predicted_log_ratio, position_size_usd, entry_cost, status, alpaca_entry_order_id, "
            "entry_rel_straddle_a, target_rel_straddle_a, qty, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?, ?, ?, ?, ?)",
            (ticker, er_date, now.date().isoformat(), now.isoformat(), call_symbol, put_symbol,
             predicted_log_ratio, position_size_usd, entry_cost, order_id,
             entry_rel_straddle_a, target_rel_straddle_a, qty, notes),
        )


def record_trade_exit(trade_id, exit_value, order_id, notes=""):
    with get_db() as conn:
        trade = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
        if trade is None:
            return
        entry_cost = trade["entry_cost"] or 0
        pnl_usd = (exit_value - entry_cost) * (trade["position_size_usd"] / entry_cost) if entry_cost else None
        pnl_pct = (exit_value - entry_cost) / entry_cost * 100 if entry_cost else None
        conn.execute(
            "UPDATE trades SET exit_date = ?, exit_value = ?, pnl_usd = ?, pnl_pct = ?, "
            "status = 'closed', alpaca_exit_order_id = ?, notes = notes || ? WHERE id = ?",
            (date.today().isoformat(), exit_value, pnl_usd, pnl_pct, order_id, ("; " + notes if notes else ""), trade_id),
        )


def get_all_trades():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM trades ORDER BY entry_date DESC").fetchall()
        return [dict(r) for r in rows]


def get_open_positions():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM trades WHERE status = 'open' ORDER BY entry_date DESC").fetchall()
        return [dict(r) for r in rows]


def _previous_option_closes(option_symbols: list) -> dict:
    """Yesterday's (or the most recent completed session's) closing price
    per option symbol, straight from Alpaca's historical option BARS
    endpoint -- get_option_bars, distinct from get_option_latest_quote/
    get_option_snapshot. OptionsSnapshot has no previous-close field the
    way a stock Snapshot does, but the bars endpoint answers "what did
    this contract close at on its last session" directly, on demand, with
    no local storage needed. A symbol is simply absent from the result if
    its most recent session had no trades at all (can happen for a
    less-liquid near-the-money contract) or the request fails."""
    if not option_symbols:
        return {}
    from alpaca.data.requests import OptionBarsRequest
    from alpaca.data.timeframe import TimeFrame
    client = get_option_data_client()
    today = date.today()
    req = OptionBarsRequest(
        symbol_or_symbols=option_symbols,
        timeframe=TimeFrame.Day,
        start=datetime.combine(today - timedelta(days=10), datetime.min.time()),  # covers weekends/holidays
    )
    try:
        bar_set = client.get_option_bars(req)
    except Exception as e:
        print(f"Live position pricing: previous-close option bars failed: {e}")
        return {}

    result = {}
    for sym, bars in (bar_set.data or {}).items():
        prior = [b for b in bars if b.timestamp.date() < today]
        if prior:
            result[sym] = float(max(prior, key=lambda b: b.timestamp).close)
    return result


def enrich_positions_live(positions: list) -> list:
    """Adds a live mark to each open position: current_straddle_price /
    current_value_usd (live call+put mid quotes, same per-contract-pair
    units as entry_cost -- see the qty*100 comment at place_straddle_entry
    for why *100), unrealized_pnl_pct/usd against entry_cost,
    position_change_pct/usd (this position's OWN change since its most
    recent completed session, via _previous_option_closes -- see that
    function's docstring for how this gets around OptionsSnapshot not
    having a previous-close field), and the underlying's own
    stock_price/stock_change_pct as a secondary reference point.

    Never raises -- a batch failure just means the affected fields are
    left out of the returned dicts, so the caller can still show the
    static (entry-time) fields.
    """
    if not positions:
        return []

    enriched = [dict(p) for p in positions]

    tickers = list(dict.fromkeys(p["ticker"] for p in enriched))
    stock_prices = {}
    try:
        from alpaca.data.historical.stock import StockHistoricalDataClient
        from alpaca.data.requests import StockSnapshotRequest
        stock_client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
        snaps = stock_client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=tickers))
        for sym, snap in snaps.items():
            try:
                price = float(snap.latest_trade.price)
                prev_close = float(snap.previous_daily_bar.close)
                change_pct = ((price - prev_close) / prev_close * 100) if prev_close else None
                stock_prices[sym] = {"price": price, "change_pct": change_pct}
            except Exception:
                continue
    except Exception as e:
        print(f"Live position pricing: stock snapshot failed: {e}")

    option_symbols = list(dict.fromkeys(
        sym for p in enriched for sym in (p["call_symbol"], p["put_symbol"]) if sym
    ))

    option_mids = {}
    try:
        from alpaca.data.requests import OptionLatestQuoteRequest
        if option_symbols:
            quote_client = get_option_data_client()
            quotes = quote_client.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=option_symbols))
            for sym, q in quotes.items():
                bid, ask = float(q.bid_price), float(q.ask_price)
                option_mids[sym] = (bid + ask) / 2 if (bid > 0 and ask > 0) else (ask or bid)
    except Exception as e:
        print(f"Live position pricing: option quote batch failed: {e}")

    prev_closes = _previous_option_closes(option_symbols)

    now_iso = datetime.now().isoformat()
    for row in enriched:
        call_mid = option_mids.get(row.get("call_symbol"))
        put_mid = option_mids.get(row.get("put_symbol"))
        if call_mid is not None and put_mid is not None:
            current_straddle_price = call_mid + put_mid
            qty = row.get("qty") or 1
            row["current_straddle_price"] = current_straddle_price
            row["current_value_usd"] = current_straddle_price * qty * 100
            entry_cost = row.get("entry_cost")
            if entry_cost:
                row["unrealized_pnl_pct"] = (current_straddle_price - entry_cost) / entry_cost * 100
                row["unrealized_pnl_usd"] = (current_straddle_price - entry_cost) * qty * 100

            call_prev = prev_closes.get(row.get("call_symbol"))
            put_prev = prev_closes.get(row.get("put_symbol"))
            if call_prev is not None and put_prev is not None:
                prev_straddle_price = call_prev + put_prev
                if prev_straddle_price:
                    row["position_change_pct"] = (current_straddle_price - prev_straddle_price) / prev_straddle_price * 100
                    row["position_change_usd"] = (current_straddle_price - prev_straddle_price) * qty * 100

        sdata = stock_prices.get(row["ticker"])
        if sdata:
            row["stock_price"] = sdata["price"]
            row["stock_change_pct"] = sdata["change_pct"]

        row["live_as_of"] = now_iso

    return enriched


def get_recent_signals(limit=200):
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM signals ORDER BY checked_at DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]


def get_performance_summary():
    trades = get_all_trades()
    closed = [t for t in trades if t["status"] == "closed" and t["pnl_pct"] is not None]
    return {
        "total_trades": len(trades),
        "open_positions": len([t for t in trades if t["status"] == "open"]),
        "closed_trades": len(closed),
        "win_rate_pct": round(sum(1 for t in closed if t["pnl_pct"] > 0) / len(closed) * 100, 1) if closed else None,
        "avg_pnl_pct": round(sum(t["pnl_pct"] for t in closed) / len(closed), 1) if closed else None,
        "total_pnl_usd": round(sum(t["pnl_usd"] for t in closed if t["pnl_usd"] is not None), 2) if closed else 0.0,
    }


NOTIFY_CONFIG_FILE = Path(__file__).parent / "paper_trading_notify_config.json"


def load_notify_config() -> dict:
    """Separate on/off switch from the existing earnings-alerts toggle --
    that one also owns the push subscribe/unsubscribe flow (see
    SettingsScreen.jsx), so it can't double as a trade-notifications switch
    without also risking unsubscribing the device entirely. This just gates
    whether notify_trade() actually sends, using the same underlying
    subscription either way. Defaults to on since trade notifications were
    already working before this toggle existed.
    """
    try:
        if NOTIFY_CONFIG_FILE.exists():
            return json.loads(NOTIFY_CONFIG_FILE.read_text())
    except Exception:
        pass
    return {"enabled": True}


def save_notify_config(config: dict):
    NOTIFY_CONFIG_FILE.write_text(json.dumps(config))


def notify_trade(title: str, body: str):
    """Push a notification for a real buy/sell action, in the exact same
    format (and to the exact same subscriber list) as the existing
    /alerts push notifications -- see notifications.py. Never raises: a
    push failure should never be allowed to break the trade it's reporting
    on, since by the time this is called the actual order has already gone
    through.
    """
    try:
        if not load_notify_config().get("enabled", True):
            return
        notifications.send_push_to_all(title, body)
    except Exception as e:
        print(f"Trade notification error: {e}")


# ---------------------------------------------------------------------------
# dbe computation (mirrors the frontend's tradingDaysUntil logic in
# EarningsScreen.jsx, ported to Python so the server can decide on its own
# without depending on the client)
# ---------------------------------------------------------------------------

def _is_weekend(d):
    return d.weekday() >= 5  # Sat=5, Sun=6


def compute_dbe(er_date_str, er_time, today=None):
    """Trading days between today and the last day you could still act
    before the print (mirrors EarningsScreen.jsx's tradingDaysUntil).
    Does not account for market holidays -- same limitation as the existing
    /alerts cron, which also uses a fixed calendar. Good enough for now,
    worth revisiting if a holiday-heavy earnings week produces a wrong dbe.
    """
    today = today or date.today()
    er_date = datetime.strptime(er_date_str, "%Y-%m-%d").date()
    last_day_to_act = er_date
    if er_time == "BMO":
        last_day_to_act -= timedelta(days=1)
        while _is_weekend(last_day_to_act):
            last_day_to_act -= timedelta(days=1)

    start_day = today
    while _is_weekend(start_day):
        start_day += timedelta(days=1)

    if last_day_to_act < start_day:
        return None  # already past the actionable window

    count = 0
    cursor = start_day
    while cursor <= last_day_to_act:
        if not _is_weekend(cursor):
            count += 1
        cursor += timedelta(days=1)

    return max(count - 1, 0) if er_time == "BMO" else count


# ---------------------------------------------------------------------------
# Live feature computation (Alpaca market data)
# ---------------------------------------------------------------------------

def find_atm_option_pair(ticker, target_dte_days, as_of=None):
    """Finds the closest-to-the-money call and put for `ticker`, on the
    weekly expiration nearest `target_dte_days` out -- same idea as
    combined_daily's daily ATM re-pick, just done live against Alpaca's
    option contract list instead of a Massive/Polygon archive.

    Returns (call_symbol, put_symbol, expiration_date, strike).
    """
    from alpaca.trading.requests import GetOptionContractsRequest
    as_of = as_of or date.today()
    target_exp = as_of + timedelta(days=target_dte_days)

    client = get_trading_client()
    stock_price = get_latest_stock_price(ticker)

    # Paginate through ALL pages -- a chain as large as SPY's (many strikes x
    # many expirations, including daily expirations) can span multiple pages
    # of Alpaca's contract list. Without this, the call and put side of the
    # correct expiration can land on different pages, making one side look
    # "missing" when it actually isn't -- that's exactly what broke on the
    # first dry run (AAPL's single-expiration weekly chain worked fine; SPY's
    # much larger daily-expiration chain did not).
    contracts = []
    page_token = None
    for _ in range(20):  # hard cap so a bug elsewhere can't loop forever
        req = GetOptionContractsRequest(
            underlying_symbols=[ticker],
            expiration_date_gte=as_of.isoformat(),
            expiration_date_lte=(target_exp + timedelta(days=4)).isoformat(),
            strike_price_gte=str(round(stock_price * 0.9, 2)),
            strike_price_lte=str(round(stock_price * 1.1, 2)),
            status="active",
            page_token=page_token,
        )
        resp = client.get_option_contracts(req)
        contracts.extend(resp.option_contracts)
        page_token = getattr(resp, "next_page_token", None)
        if not page_token:
            break

    if not contracts:
        raise RuntimeError(f"No option contracts found for {ticker} near {target_exp}")

    # nearest expiration to target, then closest strike to spot, per side
    exps = sorted({c.expiration_date for c in contracts})
    best_exp = min(exps, key=lambda e: abs((e - target_exp).days))
    same_exp = [c for c in contracts if c.expiration_date == best_exp]

    calls = [c for c in same_exp if c.type == "call"]
    puts = [c for c in same_exp if c.type == "put"]
    if not calls or not puts:
        raise RuntimeError(f"Missing call or put side for {ticker} at {best_exp}")

    # Bracket the stock price rather than picking "closest to spot"
    # independently per side. Verified against every real contract we've
    # pulled from combined_daily (GME, NFLX, TWLO, MRNA, LLY, and ~15 others):
    # the call strike is always exactly one increment ABOVE the put strike,
    # never equal -- i.e. call = nearest listed strike >= spot, put = nearest
    # listed strike <= spot. Picking "closest absolute distance" per side
    # independently (the old logic) can accidentally converge on the SAME
    # strike for both legs whenever spot sits closer to one strike than any
    # other on both sides at once -- which is what happened with AAPL here --
    # and more importantly doesn't match the convention the model was
    # actually trained on for cases where it doesn't coincidentally converge.
    calls_at_or_above = [c for c in calls if float(c.strike_price) >= stock_price]
    best_call = min(calls_at_or_above, key=lambda c: float(c.strike_price)) if calls_at_or_above \
        else max(calls, key=lambda c: float(c.strike_price))

    puts_at_or_below = [c for c in puts if float(c.strike_price) <= stock_price]
    best_put = max(puts_at_or_below, key=lambda c: float(c.strike_price)) if puts_at_or_below \
        else min(puts, key=lambda c: float(c.strike_price))

    return best_call.symbol, best_put.symbol, best_exp, float(best_call.strike_price)


def get_latest_stock_price(ticker):
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.data.requests import StockLatestTradeRequest
    client = StockHistoricalDataClient(ALPACA_API_KEY, ALPACA_SECRET_KEY)
    trade = client.get_stock_latest_trade(StockLatestTradeRequest(symbol_or_symbols=[ticker]))
    return float(trade[ticker].price)


def get_latest_option_quote_mid(symbol):
    from alpaca.data.requests import OptionLatestQuoteRequest
    client = get_option_data_client()
    q = client.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=[symbol]))[symbol]
    bid, ask = float(q.bid_price), float(q.ask_price)
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return ask or bid


def compute_live_features(ticker, dbe):
    """Builds the same feature vector the model was trained on, sourced
    from Alpaca's live market data instead of the historical archive.
    Some training features (callvolume_a, calltrans_a, putvolume_a,
    puttrans_a and similar transaction-count fields) aren't cleanly
    available from a live quote the same way -- left as NaN, which
    HistGradientBoostingRegressor handles natively (see
    ml_model_v2_documentation.md). This trades a small amount of feature
    completeness for not blocking on data Alpaca's basic feed doesn't
    expose; revisit if it turns out to matter.
    """
    call_sym, put_sym, exp_date, strike = find_atm_option_pair(ticker, target_dte_days=5)
    spy_call_sym, spy_put_sym, spy_exp, _ = find_atm_option_pair(
        "SPY", target_dte_days=(exp_date - date.today()).days
    )

    call_px = get_latest_option_quote_mid(call_sym)
    put_px = get_latest_option_quote_mid(put_sym)
    spy_call_px = get_latest_option_quote_mid(spy_call_sym)
    spy_put_px = get_latest_option_quote_mid(spy_put_sym)

    stock_close = get_latest_stock_price(ticker)
    spy_close = get_latest_stock_price("SPY")

    closestraddle_a = call_px + put_px
    closespystraddle_a = spy_call_px + spy_put_px
    rel_straddle_a = closestraddle_a / closespystraddle_a if closespystraddle_a else np.nan
    calldte_a = (exp_date - date.today()).days

    feat = {
        "dbe": dbe,
        "calldte_a": calldte_a,
        "calldte_b": np.nan,          # back-month leg not computed live yet -- see note below
        "closestraddle_a": closestraddle_a,
        "closestraddle_b": np.nan,
        "rel_straddle_a": rel_straddle_a,
        "rel_straddle_b": np.nan,
        "chg_straddle_a": np.nan,     # would need yesterday's live close cached; not tracked yet
        "chg_straddle_b": np.nan,
        "callclose_a": call_px,
        "putclose_a": put_px,
        "callclose_b": np.nan,
        "putclose_b": np.nan,
        "callvolume_a": np.nan,
        "calltrans_a": np.nan,
        "putvolume_a": np.nan,
        "puttrans_a": np.nan,
        "stock_close": stock_close,
        "stock_volume": np.nan,
        "stockchg": np.nan,
        "spy_close": spy_close,
        "spychg": np.nan,
        "closespystraddle_a": closespystraddle_a,
        "chg_spystraddle_a": np.nan,
        "days_ahead": dbe,       # entry_dbe - exit_dbe(=0)
        "exit_dbe": 0,
    }
    return feat, call_sym, put_sym, closestraddle_a

# NOTE on the _b (back-month) and chg_* fields being NaN: the training set
# uses them and they do carry some signal (chg_straddle_a/b show up in
# feature importance, though well behind exit_dbe/days_ahead). Filling them
# in live means also fetching the back-month contract pair and caching
# yesterday's close per ticker so today's change can be computed. Left as a
# follow-up rather than blocking this build -- the model handles missing
# values, so this degrades gracefully rather than breaking, but it's worth
# closing this gap before trusting live signals as much as the backtest.


def parse_occ_expiration(symbol):
    """OCC option symbols end with a fixed 15-char suffix regardless of how
    long the ticker is: 6-digit date (YYMMDD) + 1-char type (C/P) + 8-digit
    strike. Pulling the date back out of a symbol we already hold avoids
    needing a schema change just to remember each position's expiration.
    """
    date_str = symbol[-15:-9]
    return datetime.strptime(date_str, "%y%m%d").date()


def get_live_rel_straddle_for_position(call_symbol, put_symbol):
    """Re-quotes the HELD contracts (not a fresh ATM pick -- we already own
    these) and re-picks a fresh ATM SPY straddle at a comparable expiration,
    to compute today's rel_straddle_a for an open position -- the same
    SPY-normalized ratio the entry target was set in, recomputed daily the
    same way the historical data recomputes it (fresh ATM SPY strikes each
    day, not the same SPY strikes locked in at entry).

    Returns (closestraddle_a, rel_straddle_a) -- rel_straddle_a is None if
    the SPY leg can't be priced for some reason, so callers can skip the
    target check for that day rather than crashing the whole daily run.
    """
    call_px = get_latest_option_quote_mid(call_symbol)
    put_px = get_latest_option_quote_mid(put_symbol)
    closestraddle_a = call_px + put_px

    exp_date = parse_occ_expiration(call_symbol)
    remaining_dte = max((exp_date - date.today()).days, 0)
    spy_call_sym, spy_put_sym, _, _ = find_atm_option_pair("SPY", target_dte_days=remaining_dte)
    spy_call_px = get_latest_option_quote_mid(spy_call_sym)
    spy_put_px = get_latest_option_quote_mid(spy_put_sym)
    closespystraddle_a = spy_call_px + spy_put_px

    rel_straddle_a = closestraddle_a / closespystraddle_a if closespystraddle_a else None
    return closestraddle_a, rel_straddle_a


def mark_trade_unfilled_expired(trade_id, notes=""):
    with get_db() as conn:
        conn.execute(
            "UPDATE trades SET exit_date = ?, status = 'expired_unfilled', notes = notes || ? WHERE id = ?",
            (date.today().isoformat(), ("; " + notes if notes else ""), trade_id),
        )


def has_open_position(symbol):
    """True only if a REAL, filled position exists for this option symbol --
    an accepted-but-unfilled order does not count. Learned the hard way: a
    resting limit order (e.g. submitted while markets are closed, or an
    illiquid strike that never traded at our price) can sit open indefinitely
    with no position behind it. Attempting to "close" that with an opposite
    order trips Alpaca's wash-trade protection (rejects with "potential wash
    trade detected... opposite side market/stop order exists") since it looks
    like simultaneously buying and selling the same contract. Checking for a
    real position first avoids ever hitting that path in production.
    """
    client = get_trading_client()
    try:
        client.get_open_position(symbol)
        return True
    except Exception:
        return False


def cancel_open_orders_for_symbols(*symbols):
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus

    client = get_trading_client()
    cancelled = []
    for o in client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN)):
        leg_symbols = {leg.symbol for leg in o.legs} if getattr(o, "legs", None) else {getattr(o, "symbol", None)}
        if leg_symbols & set(symbols):
            client.cancel_order_by_id(o.id)
            cancelled.append(str(o.id))
    return cancelled


# ---------------------------------------------------------------------------
# Order placement
# ---------------------------------------------------------------------------

def place_straddle_entry(call_symbol, put_symbol, notional_usd, limit_price):
    """Submits a multi-leg (Level 3) order: buy 1 call + 1 put as one
    combo order. UNTESTED against a live account -- verify this call shape
    against your installed alpaca-py version before trusting it.
    """
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce

    client = get_trading_client()
    qty = max(int(notional_usd // (limit_price * 100)), 1)  # 1 contract = 100 shares equiv

    order = LimitOrderRequest(
        qty=qty,
        order_class=OrderClass.MLEG,
        time_in_force=TimeInForce.DAY,
        limit_price=round(limit_price, 2),
        legs=[
            OptionLegRequest(symbol=call_symbol, side=OrderSide.BUY, ratio_qty=1),
            OptionLegRequest(symbol=put_symbol, side=OrderSide.BUY, ratio_qty=1),
        ],
    )
    return client.submit_order(order), qty


def close_straddle(call_symbol, put_symbol, qty=1):
    """Closes both legs. `qty` must match how many contracts were actually
    bought at entry -- this used to be hardcoded to 1 regardless of real
    position size, which would only partially close (or reject on) any
    trade sized to more than 1 contract. Fixed alongside the target-exit
    work below since both exit paths call this.
    """
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce

    client = get_trading_client()
    call_px = get_latest_option_quote_mid(call_symbol)
    put_px = get_latest_option_quote_mid(put_symbol)

    order = LimitOrderRequest(
        qty=qty,
        order_class=OrderClass.MLEG,
        time_in_force=TimeInForce.DAY,
        limit_price=round(call_px + put_px, 2),
        legs=[
            OptionLegRequest(symbol=call_symbol, side=OrderSide.SELL, ratio_qty=1),
            OptionLegRequest(symbol=put_symbol, side=OrderSide.SELL, ratio_qty=1),
        ],
    )
    return client.submit_order(order), call_px + put_px


# ---------------------------------------------------------------------------
# Daily check -- entry point for the cron job
# ---------------------------------------------------------------------------

def run_daily_check(upcoming_earnings):
    """`upcoming_earnings` is the same {ticker: {date, time}} shape the
    frontend already builds from GET /earnings. Despite the name, this is
    now called every few minutes during market hours by the
    insignia-paper-trading cron entry in render.yaml -- "daily" describes
    the original design, not the current call cadence. A market-hours guard
    below makes off-hours/weekend invocations a cheap near-instant no-op
    rather than doing real work against stale or unavailable quotes.

    Exit logic has two layers:
      1. Target exit: on every call while a position is open and dbe > 0,
         re-quote the held contracts and re-pick a fresh ATM SPY straddle to
         compute the current rel_straddle_a, and sell as soon as it reaches
         the target set at entry (target_rel_straddle_a = entry_rel_straddle_a
         * exp(predicted_log_ratio) -- the model's own predicted move, turned
         into a concrete level to sell at instead of waiting blindly).
      2. Backstop exit: dbe == 0 always exits regardless of the target --
         holding through the actual earnings print was never part of this
         strategy and changes the risk profile entirely.
    """
    client = get_trading_client()
    clock = client.get_clock()
    if not clock.is_open:
        # Nothing to do outside market hours -- option quotes are stale or
        # unavailable, and dbe (a whole-trading-day count) can't change
        # between now and the next open anyway. Returning immediately here,
        # before init_db()/get_model() even run, is what makes polling this
        # every few minutes around the clock cheap rather than wasteful.
        return {"entries": [], "exits": [], "skipped": [], "errors": [], "market_open": False}

    init_db()
    model, feature_names = get_model()
    account = client.get_account()
    equity = float(account.equity)

    results = {"entries": [], "exits": [], "skipped": [], "errors": [], "market_open": True}

    # --- exits: target hit, or the dbe==0 backstop ---
    for trade in get_open_positions():
        info = upcoming_earnings.get(trade["ticker"])
        dbe = compute_dbe(info["date"], info.get("time", "TBD")) if info else None
        qty = trade.get("qty") or 1

        if dbe == 0:
            try:
                call_filled = has_open_position(trade["call_symbol"])
                put_filled = has_open_position(trade["put_symbol"])
                if not (call_filled and put_filled):
                    # entry order never actually filled -- there's nothing to
                    # close. Cancel any still-resting order on these legs and
                    # record the trade honestly instead of treating it as a
                    # closed position with real P&L.
                    cancelled = cancel_open_orders_for_symbols(trade["call_symbol"], trade["put_symbol"])
                    mark_trade_unfilled_expired(
                        trade["id"],
                        notes=f"entry never filled by dbe=0 (call_filled={call_filled}, put_filled={put_filled}); cancelled orders: {cancelled}",
                    )
                    results["skipped"].append({"ticker": trade["ticker"], "reason": "entry never filled -- expired unfilled at dbe=0"})
                    continue
                order, exit_value = close_straddle(trade["call_symbol"], trade["put_symbol"], qty=qty)
                record_trade_exit(trade["id"], exit_value, str(order.id), notes="backstop exit at dbe=0")
                results["exits"].append({"ticker": trade["ticker"], "exit_value": exit_value, "reason": "dbe_backstop"})
                pnl_pct = (exit_value - trade["entry_cost"]) / trade["entry_cost"] * 100 if trade.get("entry_cost") else None
                pnl_str = f" ({pnl_pct:+.1f}%)" if pnl_pct is not None else ""
                notify_trade(
                    f"Insignia Sell — {trade['ticker']}",
                    f"Sold {trade['ticker']} straddle ahead of earnings (mandatory exit). Exit value: ${exit_value:,.2f}{pnl_str}.",
                )
            except Exception as e:
                results["errors"].append({"ticker": trade["ticker"], "stage": "exit", "error": str(e)})
            continue

        if dbe is None or dbe <= 0:
            # Ticker fell out of the earnings calendar window, or dbe is
            # negative (past the print already). Either way there's nothing
            # safe to auto-decide here -- leave it for manual review rather
            # than guessing at intent.
            continue

        if trade.get("target_rel_straddle_a") is None:
            # entered before the target-exit columns existed -- nothing to
            # check against; falls through to the dbe==0 backstop only.
            continue

        try:
            if not (has_open_position(trade["call_symbol"]) and has_open_position(trade["put_symbol"])):
                continue  # entry hasn't filled yet -- nothing to monitor
            _, rel_straddle_a = get_live_rel_straddle_for_position(trade["call_symbol"], trade["put_symbol"])
            target = trade["target_rel_straddle_a"]
            if rel_straddle_a is not None and rel_straddle_a >= target:
                order, exit_value = close_straddle(trade["call_symbol"], trade["put_symbol"], qty=qty)
                record_trade_exit(
                    trade["id"], exit_value, str(order.id),
                    notes=f"target hit early at dbe={dbe}: rel_straddle_a={rel_straddle_a:.4f} >= target={target:.4f}",
                )
                log_signal(trade["ticker"], trade["er_date"], dbe, None, "exited_target",
                           detail=f"rel_straddle_a={rel_straddle_a:.4f} target={target:.4f}")
                results["exits"].append({"ticker": trade["ticker"], "exit_value": exit_value, "reason": "target_hit"})
                pnl_pct = (exit_value - trade["entry_cost"]) / trade["entry_cost"] * 100 if trade.get("entry_cost") else None
                pnl_str = f" ({pnl_pct:+.1f}%)" if pnl_pct is not None else ""
                notify_trade(
                    f"Insignia Sell — {trade['ticker']}",
                    f"Sold {trade['ticker']} straddle early — target hit at dbe={dbe}. Exit value: ${exit_value:,.2f}{pnl_str}.",
                )
            else:
                log_signal(trade["ticker"], trade["er_date"], dbe, None, "holding",
                           detail=f"rel_straddle_a={rel_straddle_a} target={target}")
        except Exception as e:
            results["errors"].append({"ticker": trade["ticker"], "stage": "target_check", "error": str(e)})

    # --- entries: tickers currently at dbe 2-3 with no open position yet ---
    for ticker, info in upcoming_earnings.items():
        dbe = compute_dbe(info["date"], info.get("time", "TBD"))
        er_date = info["date"]
        if dbe is None or not (ENTRY_DBE_MIN <= dbe <= ENTRY_DBE_MAX):
            continue
        if get_open_trade(ticker, er_date):
            continue
        try:
            feat, call_sym, put_sym, entry_cost = compute_live_features(ticker, dbe)
            x = pd.DataFrame([{c: feat.get(c, np.nan) for c in feature_names}], columns=feature_names)
            predicted_log_ratio = float(model.predict(x)[0])

            if predicted_log_ratio < THRESHOLD:
                log_signal(ticker, er_date, dbe, predicted_log_ratio, "skipped_threshold")
                results["skipped"].append({"ticker": ticker, "reason": "below threshold", "predicted_log_ratio": predicted_log_ratio})
                continue

            position_size_usd = equity * POSITION_FRACTION
            if position_size_usd > float(account.buying_power):
                log_signal(ticker, er_date, dbe, predicted_log_ratio, "skipped_no_cash")
                results["skipped"].append({"ticker": ticker, "reason": "insufficient buying power"})
                continue

            entry_rel_straddle_a = feat.get("rel_straddle_a")
            target_rel_straddle_a = (
                entry_rel_straddle_a * float(np.exp(predicted_log_ratio))
                if entry_rel_straddle_a is not None and not np.isnan(entry_rel_straddle_a)
                else None
            )

            order, qty = place_straddle_entry(call_sym, put_sym, position_size_usd, entry_cost)
            record_trade_entry(
                ticker, er_date, call_sym, put_sym, predicted_log_ratio,
                position_size_usd, entry_cost, str(order.id),
                entry_rel_straddle_a=entry_rel_straddle_a,
                target_rel_straddle_a=target_rel_straddle_a,
                qty=qty,
            )
            log_signal(ticker, er_date, dbe, predicted_log_ratio, "entered")
            results["entries"].append({
                "ticker": ticker,
                "predicted_log_ratio": predicted_log_ratio,
                "position_size_usd": position_size_usd,
                "target_rel_straddle_a": target_rel_straddle_a,
            })
            predicted_pct = (np.exp(predicted_log_ratio) - 1) * 100
            notify_trade(
                f"Insignia Buy — {ticker}",
                f"Bought {ticker} straddle ahead of its {er_date} earnings. "
                f"Model predicts {predicted_pct:+.0f}% move, position size ${position_size_usd:,.0f}.",
            )

        except Exception as e:
            log_signal(ticker, er_date, dbe, None, "error", detail=str(e))
            results["errors"].append({"ticker": ticker, "stage": "entry", "error": str(e)})

    return results
