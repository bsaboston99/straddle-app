"""
Live-observed daily archive.

Captures Alpaca's live market/option quotes into a small SQLite table
shaped like Reverse Theta's combined_daily files, so what the live pipeline
actually saw each day can be exported and looked at later -- extending the
historical archive generally, not feeding back into the trained model or
the paper-trading strategy.

ENTIRELY SEPARATE FROM THE EXISTING HISTORICAL DATA AND FROM THE TRADE
LEDGER -- this was a specific requirement, not an incidental design choice:
  - Its own SQLite file, LIVE_ARCHIVE_DB (see render.yaml) -- a distinct
    path on the same persistent disk paper_trading.db already uses, but a
    different file. Nothing here ever opens paper_trading.db, and nothing
    in paper_trading.py ever opens this one.
  - Nothing here reads or writes df_global, TICKER_GROUPS, or anything
    under COMBINED_DIR (Reverse Theta's combined_daily/ files) -- the only
    thing borrowed from that side is the ticker list itself (which tickers
    exist), passed in by the caller, never the historical rows.
  - Export lands in a brand-new Reverse Theta/live_daily/ folder via a
    one-way pull script the user runs locally (Code/sync_live_archive.py).
    Nothing here writes into stock_daily/, options_daily/, or
    combined_daily/, and parquetcombine.py never reads live_daily/ --
    merging the two archives, if that's ever wanted, is a deliberate step
    taken later, not something this module or that script does silently.

SCHEMA: mirrors combined_daily's column names so the two are easy to
compare side by side. Columns that don't exist for a point-in-time quote
(open/high/low/volume/transactions *bars*) are simply absent rather than
faked -- see live_quotes.py's module docstring, point 4: Alpaca's options
data here is an indicative bid/ask mid, not a real trade print, and that
caveat applies to every *open_a / *close_a / etc. column below. Stock
open/close ARE real trade prints (Alpaca's stock snapshot), same as the
historical data.

CAPTURE FLOW -- two Render crons hit /live-archive/capture-open and
/live-archive/capture-close once each per trading day (see render.yaml):
  1. capture_open(): for every ticker, look up its nearest two FRIDAY
     expirations' OTM call/put contracts. This is one Alpaca contracts
     call per ticker -- inherently per-underlying, can't be batched -- but
     every leg's mid quote across the WHOLE ticker universe is then
     fetched in a handful of batched calls, not one batch per ticker. The
     chosen contract symbols are persisted in the DB row so
     capture_close() can reuse them without a second contracts lookup --
     this has to go through the DB rather than an in-memory cache, since
     Render runs each cron as a separate call into the running web
     service, hours apart.
  2. capture_close(): reads back the symbols capture_open() already
     picked for today and re-quotes only those (a handful of batched
     calls, no contracts lookup) -- falls back to a fresh per-ticker
     lookup only for a ticker capture_open() missed entirely.
"""
import os
import sqlite3
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import date, datetime, timedelta
from pathlib import Path

import paper_trading
from live_quotes import _pick_otm_pair, _quote_mid

DB_PATH = Path(os.environ.get(
    "LIVE_ARCHIVE_DB",
    Path(__file__).parent / "data" / "live_archive.db"
))

# Practical chunk size for Alpaca's multi-symbol quote/snapshot requests --
# same defensive chunking main.py already uses for stock snapshots.
CHUNK = 200

LEG_SUFFIXES = ("a", "b")


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
            CREATE TABLE IF NOT EXISTS live_daily (
                ticker TEXT NOT NULL,
                date TEXT NOT NULL,
                dbe INTEGER,
                er_date TEXT,
                er_tod TEXT,
                stock_open REAL,
                stock_close REAL,
                callexp_a TEXT, calldte_a INTEGER, callsym_a TEXT, callopen_a REAL, callclose_a REAL,
                putsym_a TEXT, putopen_a REAL, putclose_a REAL,
                callexp_b TEXT, calldte_b INTEGER, callsym_b TEXT, callopen_b REAL, callclose_b REAL,
                putsym_b TEXT, putopen_b REAL, putclose_b REAL,
                spy_open REAL, spy_close REAL,
                spycallsym_a TEXT, spycallopen_a REAL, spycallclose_a REAL,
                spyputsym_a TEXT, spyputopen_a REAL, spyputclose_a REAL,
                spycallsym_b TEXT, spycallopen_b REAL, spycallclose_b REAL,
                spyputsym_b TEXT, spyputopen_b REAL, spyputclose_b REAL,
                closestraddle_a REAL, closestraddle_b REAL,
                closespystraddle_a REAL, closespystraddle_b REAL,
                captured_open_at TEXT,
                captured_close_at TEXT,
                source TEXT DEFAULT 'alpaca_live',
                PRIMARY KEY (ticker, date)
            )
        """)


def _upsert_row(conn, row: dict):
    """INSERT ... ON CONFLICT DO UPDATE, touching only the columns present
    in `row` -- so capture_open() only ever writes open-side columns and
    capture_close() only ever writes close-side columns, without either
    one clobbering fields the other already wrote for the same day."""
    cols = list(row.keys())
    col_list = ", ".join(cols)
    placeholders = ", ".join("?" for _ in cols)
    updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c not in ("ticker", "date"))
    conn.execute(
        f"INSERT INTO live_daily ({col_list}) VALUES ({placeholders}) "
        f"ON CONFLICT(ticker, date) DO UPDATE SET {updates}",
        [row[c] for c in cols],
    )


# ---------------------------------------------------------------------------
# Alpaca lookups
# ---------------------------------------------------------------------------

def _batch_stock_prices(tickers: list) -> dict:
    """{symbol: latest_trade_price} for every ticker + SPY, in as few
    batched snapshot calls as possible -- same pattern main.py's
    /watchlist-live already uses."""
    from alpaca.data.historical.stock import StockHistoricalDataClient
    from alpaca.data.requests import StockSnapshotRequest
    client = StockHistoricalDataClient(paper_trading.ALPACA_API_KEY, paper_trading.ALPACA_SECRET_KEY)
    prices = {}
    all_syms = list(dict.fromkeys(tickers + ["SPY"]))
    for i in range(0, len(all_syms), CHUNK):
        chunk = all_syms[i:i + CHUNK]
        try:
            snaps = client.get_stock_snapshot(StockSnapshotRequest(symbol_or_symbols=chunk))
        except Exception as e:
            print(f"Live archive: stock snapshot chunk failed starting {chunk[0]}: {e}")
            continue
        for sym, snap in snaps.items():
            try:
                prices[sym] = float(snap.latest_trade.price)
            except Exception:
                continue
    return prices


def _discover_legs_one(ticker: str, stock_price: float):
    """Nearest two FRIDAY-listed expirations' OTM call/put contracts for
    one ticker -- see live_quotes.py point 1 for why Friday-only. One
    Alpaca contracts call (paginated) per ticker; inherently per-underlying,
    can't be batched across tickers."""
    if not stock_price:
        return []
    from alpaca.trading.requests import GetOptionContractsRequest

    today = date.today()
    client = paper_trading.get_trading_client()

    contracts = []
    page_token = None
    for _ in range(20):
        req = GetOptionContractsRequest(
            underlying_symbols=[ticker],
            expiration_date_gte=today.isoformat(),
            expiration_date_lte=(today + timedelta(days=60)).isoformat(),
            strike_price_gte=str(round(stock_price * 0.9, 2)),
            strike_price_lte=str(round(stock_price * 1.1, 2)),
            status="active",
            page_token=page_token,
        )
        try:
            resp = client.get_option_contracts(req)
        except Exception as e:
            print(f"Live archive: contracts lookup failed for {ticker}: {e}")
            break
        contracts.extend(resp.option_contracts)
        page_token = getattr(resp, "next_page_token", None)
        if not page_token:
            break

    contracts = [c for c in contracts if c.expiration_date.weekday() == 4]  # Friday-only
    if not contracts:
        return []

    exps = sorted({c.expiration_date for c in contracts})[:2]
    legs = []
    for exp in exps:
        same_exp = [c for c in contracts if c.expiration_date == exp]
        pair = _pick_otm_pair(same_exp, stock_price)
        if pair is None:
            continue
        best_call, best_put = pair
        legs.append({
            "expiration": exp,
            "dte": (exp - today).days,
            "call_symbol": best_call.symbol,
            "put_symbol": best_put.symbol,
        })
    return legs


def _discover_spy_legs(exp_dates: list, spy_price: float) -> dict:
    """SPY's OTM call/put contracts at each EXACT expiration date in
    `exp_dates` -- SPY quoted at the tickers' own dates, never
    independently ranked (live_quotes.py point 2). One contracts call per
    distinct date; most tickers share the same one or two nearest Fridays,
    so this is usually just a handful of calls total, not one per ticker."""
    if not exp_dates or not spy_price:
        return {}
    from alpaca.trading.requests import GetOptionContractsRequest
    client = paper_trading.get_trading_client()

    result = {}
    for exp in exp_dates:
        contracts = []
        page_token = None
        for _ in range(20):
            req = GetOptionContractsRequest(
                underlying_symbols=["SPY"],
                expiration_date=exp.isoformat(),
                strike_price_gte=str(round(spy_price * 0.9, 2)),
                strike_price_lte=str(round(spy_price * 1.1, 2)),
                status="active",
                page_token=page_token,
            )
            try:
                resp = client.get_option_contracts(req)
            except Exception as e:
                print(f"Live archive: SPY contracts lookup failed for {exp}: {e}")
                break
            contracts.extend(resp.option_contracts)
            page_token = getattr(resp, "next_page_token", None)
            if not page_token:
                break
        pair = _pick_otm_pair(contracts, spy_price)
        if pair:
            best_call, best_put = pair
            result[exp] = {"call_symbol": best_call.symbol, "put_symbol": best_put.symbol}
    return result


def _batch_mids(symbols: list) -> dict:
    """Mid price for every symbol in `symbols`, deduped, in as few batched
    Alpaca calls as possible -- the whole point of doing this once across
    the full ticker universe instead of per-ticker (see module docstring)."""
    if not symbols:
        return {}
    from alpaca.data.requests import OptionLatestQuoteRequest
    client = paper_trading.get_option_data_client()
    mids = {}
    uniq = list(dict.fromkeys(symbols))
    for i in range(0, len(uniq), CHUNK):
        chunk = uniq[i:i + CHUNK]
        try:
            quotes = client.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=chunk))
        except Exception as e:
            print(f"Live archive: batched option quote chunk failed: {e}")
            continue
        for sym, q in quotes.items():
            mids[sym] = _quote_mid(q)
    return mids


def _earnings_lookup(tickers: list, get_earnings_fn) -> dict:
    """{ticker: (er_date_str, er_tod)} for each ticker's soonest upcoming
    earnings print, reusing the same NASDAQ earnings calendar
    /watchlist-live already pulls. `get_earnings_fn` is main.get_earnings,
    passed in rather than imported to avoid a circular import between
    main.py and this module."""
    lookup = {}
    try:
        resp = get_earnings_fn(universe="all", weeks=8)
        dated = []
        for date_str, items in resp.get("grouped", {}).items():
            for item in items:
                dated.append((date_str, item["ticker"], item.get("time", "TBD")))
        dated.sort(key=lambda x: x[0])
        for d, t, tm in dated:
            if t not in lookup:
                lookup[t] = (d, tm)
    except Exception as e:
        print(f"Live archive: earnings lookup failed, er_date/dbe will be null: {e}")
    return lookup


def _compute_dbe(er_date, er_tod):
    if not er_date:
        return None
    try:
        return paper_trading.compute_dbe(er_date, er_tod or "TBD")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Capture
# ---------------------------------------------------------------------------

def capture_open(tickers: list, get_earnings_fn) -> dict:
    today = date.today().isoformat()
    now_iso = datetime.now().isoformat()

    stock_prices = _batch_stock_prices(tickers)
    spy_price = stock_prices.get("SPY")
    if not spy_price:
        raise RuntimeError("Live archive: no SPY price available, aborting open capture")

    legs_by_ticker = {}
    with ThreadPoolExecutor(max_workers=15) as ex:
        futures = {ex.submit(_discover_legs_one, t, stock_prices.get(t)): t for t in tickers}
        for fut in as_completed(futures):
            t = futures[fut]
            try:
                legs = fut.result()
                if legs:
                    legs_by_ticker[t] = legs
            except Exception as e:
                print(f"Live archive: leg discovery failed for {t}: {e}")

    distinct_dates = sorted({leg["expiration"] for legs in legs_by_ticker.values() for leg in legs})
    spy_legs = _discover_spy_legs(distinct_dates, spy_price)

    all_symbols = []
    for legs in legs_by_ticker.values():
        for leg in legs:
            all_symbols += [leg["call_symbol"], leg["put_symbol"]]
    for sl in spy_legs.values():
        all_symbols += [sl["call_symbol"], sl["put_symbol"]]
    mids = _batch_mids(all_symbols)

    earnings_lookup = _earnings_lookup(tickers, get_earnings_fn)

    captured = 0
    with get_db() as conn:
        for ticker, legs in legs_by_ticker.items():
            er_date, er_tod = earnings_lookup.get(ticker, (None, None))
            row = {
                "ticker": ticker,
                "date": today,
                "dbe": _compute_dbe(er_date, er_tod),
                "er_date": er_date,
                "er_tod": er_tod,
                "stock_open": stock_prices.get(ticker),
                "spy_open": spy_price,
                "captured_open_at": now_iso,
                "source": "alpaca_live",
            }
            for suffix, leg in zip(LEG_SUFFIXES, legs):
                row[f"callexp_{suffix}"] = leg["expiration"].isoformat()
                row[f"calldte_{suffix}"] = leg["dte"]
                row[f"callsym_{suffix}"] = leg["call_symbol"]
                row[f"putsym_{suffix}"] = leg["put_symbol"]
                row[f"callopen_{suffix}"] = mids.get(leg["call_symbol"])
                row[f"putopen_{suffix}"] = mids.get(leg["put_symbol"])
                spy_leg = spy_legs.get(leg["expiration"])
                if spy_leg:
                    row[f"spycallsym_{suffix}"] = spy_leg["call_symbol"]
                    row[f"spyputsym_{suffix}"] = spy_leg["put_symbol"]
                    row[f"spycallopen_{suffix}"] = mids.get(spy_leg["call_symbol"])
                    row[f"spyputopen_{suffix}"] = mids.get(spy_leg["put_symbol"])
            _upsert_row(conn, row)
            captured += 1

    return {"captured": captured, "requested": len(tickers), "at": now_iso}


def capture_close(tickers: list, get_earnings_fn) -> dict:
    today = date.today().isoformat()
    now_iso = datetime.now().isoformat()

    with get_db() as conn:
        placeholders = ",".join("?" * len(tickers))
        existing = {
            r["ticker"]: dict(r)
            for r in conn.execute(
                f"SELECT * FROM live_daily WHERE date = ? AND ticker IN ({placeholders})",
                [today] + tickers,
            )
        }

    missing = [t for t in tickers if not existing.get(t, {}).get("callsym_a")]

    stock_prices = _batch_stock_prices(tickers)
    spy_price = stock_prices.get("SPY")

    # Tickers capture_open() never got legs for (it failed, or ran before
    # this ticker's row existed for some other reason) get a fresh,
    # per-ticker leg discovery here as a fallback.
    fresh_legs = {}
    if missing and spy_price:
        with ThreadPoolExecutor(max_workers=15) as ex:
            futures = {ex.submit(_discover_legs_one, t, stock_prices.get(t)): t for t in missing}
            for fut in as_completed(futures):
                t = futures[fut]
                try:
                    legs = fut.result()
                    if legs:
                        fresh_legs[t] = legs
                except Exception as e:
                    print(f"Live archive: close-time leg discovery failed for {t}: {e}")

    all_symbols = []
    for row in existing.values():
        for col in ("callsym_a", "putsym_a", "callsym_b", "putsym_b",
                    "spycallsym_a", "spyputsym_a", "spycallsym_b", "spyputsym_b"):
            if row.get(col):
                all_symbols.append(row[col])
    for legs in fresh_legs.values():
        for leg in legs:
            all_symbols += [leg["call_symbol"], leg["put_symbol"]]

    fresh_dates = sorted({leg["expiration"] for legs in fresh_legs.values() for leg in legs})
    spy_legs = _discover_spy_legs(fresh_dates, spy_price) if fresh_dates else {}
    for sl in spy_legs.values():
        all_symbols += [sl["call_symbol"], sl["put_symbol"]]

    mids = _batch_mids(all_symbols)
    earnings_lookup = _earnings_lookup(tickers, get_earnings_fn) if fresh_legs else {}

    captured = 0
    with get_db() as conn:
        for ticker in tickers:
            existing_row = existing.get(ticker)
            row = {"ticker": ticker, "date": today, "captured_close_at": now_iso}

            if existing_row and existing_row.get("callsym_a"):
                for suffix in LEG_SUFFIXES:
                    call_sym = existing_row.get(f"callsym_{suffix}")
                    put_sym = existing_row.get(f"putsym_{suffix}")
                    if call_sym:
                        row[f"callclose_{suffix}"] = mids.get(call_sym)
                    if put_sym:
                        row[f"putclose_{suffix}"] = mids.get(put_sym)
                    spy_call = existing_row.get(f"spycallsym_{suffix}")
                    spy_put = existing_row.get(f"spyputsym_{suffix}")
                    if spy_call:
                        row[f"spycallclose_{suffix}"] = mids.get(spy_call)
                    if spy_put:
                        row[f"spyputclose_{suffix}"] = mids.get(spy_put)
            elif ticker in fresh_legs:
                legs = fresh_legs[ticker]
                er_date, er_tod = earnings_lookup.get(ticker, (None, None))
                row["dbe"] = _compute_dbe(er_date, er_tod)
                row["er_date"] = er_date
                row["er_tod"] = er_tod
                row["source"] = "alpaca_live"
                for suffix, leg in zip(LEG_SUFFIXES, legs):
                    row[f"callexp_{suffix}"] = leg["expiration"].isoformat()
                    row[f"calldte_{suffix}"] = leg["dte"]
                    row[f"callsym_{suffix}"] = leg["call_symbol"]
                    row[f"putsym_{suffix}"] = leg["put_symbol"]
                    row[f"callclose_{suffix}"] = mids.get(leg["call_symbol"])
                    row[f"putclose_{suffix}"] = mids.get(leg["put_symbol"])
                    spy_leg = spy_legs.get(leg["expiration"])
                    if spy_leg:
                        row[f"spycallsym_{suffix}"] = spy_leg["call_symbol"]
                        row[f"spyputsym_{suffix}"] = spy_leg["put_symbol"]
                        row[f"spycallclose_{suffix}"] = mids.get(spy_leg["call_symbol"])
                        row[f"spyputclose_{suffix}"] = mids.get(spy_leg["put_symbol"])
            else:
                continue  # no legs from either capture today; nothing to record

            row["stock_close"] = stock_prices.get(ticker)
            row["spy_close"] = spy_price

            # Derived percentile columns, same normalization as
            # parquetcombine.py -- only once both legs of a side exist.
            stock_close = stock_prices.get(ticker)
            if stock_close:
                cc_a, pc_a = row.get("callclose_a"), row.get("putclose_a")
                if cc_a is not None and pc_a is not None:
                    row["closestraddle_a"] = (cc_a + pc_a) / stock_close
                cc_b, pc_b = row.get("callclose_b"), row.get("putclose_b")
                if cc_b is not None and pc_b is not None:
                    row["closestraddle_b"] = (cc_b + pc_b) / stock_close
            if spy_price:
                scc_a, spc_a = row.get("spycallclose_a"), row.get("spyputclose_a")
                if scc_a is not None and spc_a is not None:
                    row["closespystraddle_a"] = (scc_a + spc_a) / spy_price
                scc_b, spc_b = row.get("spycallclose_b"), row.get("spyputclose_b")
                if scc_b is not None and spc_b is not None:
                    row["closespystraddle_b"] = (scc_b + spc_b) / spy_price

            _upsert_row(conn, row)
            captured += 1

    return {"captured": captured, "requested": len(tickers), "at": now_iso}


def export_rows(since: str = None) -> list:
    """Every archived row (as plain dicts), with date >= `since` when
    given, ordered by date then ticker. Consumed by /live-archive/export
    and, from there, by the user's local Code/sync_live_archive.py, which
    writes them into Reverse Theta/live_daily/ -- see module docstring."""
    with get_db() as conn:
        if since:
            cur = conn.execute("SELECT * FROM live_daily WHERE date >= ? ORDER BY date, ticker", (since,))
        else:
            cur = conn.execute("SELECT * FROM live_daily ORDER BY date, ticker")
        return [dict(r) for r in cur.fetchall()]


def get_status() -> dict:
    """Lightweight health check: row/date counts, the most recent capture
    timestamps, and today's per-ticker coverage -- powers
    /live-archive/status so this can be checked from a browser instead of
    digging through Render logs."""
    with get_db() as conn:
        total_rows = conn.execute("SELECT COUNT(*) AS n FROM live_daily").fetchone()["n"]
        distinct_dates = conn.execute("SELECT COUNT(DISTINCT date) AS n FROM live_daily").fetchone()["n"]
        earliest_date = conn.execute("SELECT MIN(date) AS d FROM live_daily").fetchone()["d"]
        latest_date = conn.execute("SELECT MAX(date) AS d FROM live_daily").fetchone()["d"]
        last_open_at = conn.execute("SELECT MAX(captured_open_at) AS t FROM live_daily").fetchone()["t"]
        last_close_at = conn.execute("SELECT MAX(captured_close_at) AS t FROM live_daily").fetchone()["t"]

        today = date.today().isoformat()
        today_rows = [dict(r) for r in conn.execute(
            "SELECT ticker, stock_open, stock_close, callsym_a, captured_open_at, captured_close_at "
            "FROM live_daily WHERE date = ? ORDER BY ticker",
            (today,),
        )]

    today_summary = {
        "date": today,
        "tickers_captured": len(today_rows),
        "with_open": sum(1 for r in today_rows if r["stock_open"] is not None),
        "with_close": sum(1 for r in today_rows if r["stock_close"] is not None),
        "missing_legs": sorted(r["ticker"] for r in today_rows if r["callsym_a"] is None),
    }

    return {
        "db_path": str(DB_PATH),
        "db_exists": DB_PATH.exists(),
        "total_rows": total_rows,
        "distinct_dates": distinct_dates,
        "earliest_date": earliest_date,
        "latest_date": latest_date,
        "last_capture_open_at": last_open_at,
        "last_capture_close_at": last_close_at,
        "today": today_summary,
    }
