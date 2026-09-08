"""
Live options-quote helpers for the Earnings/Analysis screens, the existing
alerts feature, and the Watchlist screen -- replaces the old hardcoded
MOCK_LIVE dict in main.py with real Alpaca data.

This matches the ACTUAL historical construction in
Reverse Theta/Code/parquetcombine.py, confirmed by reading that script
directly rather than guessing from output patterns. Several rules matter
here, each confirmed against the source (or, for point 4/5, against real
account behavior / a deliberate product decision) rather than assumed:

1. Ticker expiration selection -- FRIDAY ONLY.
   The raw rule in parquetcombine.py is simply "rank all listed expirations
   by DTE ascending; nearest is 'a', second-nearest is 'b'" -- no explicit
   day-of-week filter. But the historical calldte_a/calldte_b gap for NVDA
   is dominated by 4-5 day diffs (weekly) and ~19-20 day diffs (monthly
   roll), with NO diffs under 4 days anywhere in the data. That's because,
   historically, single-name tickers like NVDA only ever had Friday-expiring
   listed options -- so "rank all listed expirations" and "rank Friday
   expirations" were the same thing.
   That stopped being true in January 2026: Cboe's Short-Term Option Series
   Program now lists Monday- and Wednesday-expiring options for large-cap
   "qualifying securities" (>$700B market cap, >10M contracts/month volume --
   NVDA and the rest of this app's watchlist all qualify). Filtering live
   selection to Friday-only expirations reproduces the cadence the model
   actually saw.

2. SPY is NOT independently ranked -- it is quoted at the TICKER'S OWN
   expiration dates.
   Confirmed by reading parquetcombine.py's SPY-merge block: it joins SPY's
   call/put quotes onto each row using the ticker's own selected "a"/"b"
   expiration dates -- not a separately-computed "SPY's nearest 2
   expirations." SPY has had daily-expiring listed options since 2022;
   independently ranking SPY's own nearest 2 expirations would almost
   always pick a far tighter, unrelated pair of dates than the ticker's
   own (Friday-spaced) pair -- comparing the ticker's straddle against the
   wrong SPY maturity entirely.

3. Every straddle value is normalized by ITS OWN underlying's spot price,
   not a raw dollar mid-price.
   Confirmed by reading parquetcombine.py's derived-column block:
   `closestraddle_a = (callclose_a + putclose_a) / stock_close` and
   `closespystraddle_a = (spycallclose_a + spyputclose_a) / spy_close`.

4. Alpaca's account-wide rate limit (200 requests/minute, confirmed via
   Alpaca's own support docs) is shared with the paper-trading cron, and
   main.py's /watchlist-live calls this module once per confirmed-earnings
   ticker. Two things keep that affordable:
   - Every option-leg quote needed for one expiration (call + put), or for
     one ticker across both its "a" and "b" expirations, is fetched in a
     SINGLE batched Alpaca call (OptionLatestQuoteRequest accepts a list of
     symbols and returns all of them at once) instead of one call per leg.
   - get_ranked_expirations/get_live_straddle_inputs accept an optional
     pre-fetched `stock_price`, so a caller that already knows the spot
     price (e.g. main.py's /watchlist-live, which fetches every ticker's
     price in one batched snapshot call anyway) doesn't pay for a second,
     redundant per-ticker price lookup here.

5. Expiration selection is ANCHORED TO THE TICKER'S OWN EARNINGS DATE, not
   to today.
   "a" is the nearest listed Friday expiration ON OR AFTER the earnings
   release (so the straddle is held through the event), "b" is the next
   listed Friday after that. Two consequences of this:
   - Only tickers with a CONFIRMED earnings date/time (NASDAQ's calendar
     reports an actual pre-market ("BMO") or after-hours ("AMC") session,
     not its "time-not-supplied" placeholder for a date that hasn't been
     locked in) can be handled here at all -- an unconfirmed date isn't a
     reliable anchor, so main.py simply doesn't call this module for those
     tickers and they fall back to the historical calc.
   - For an AMC release, "on or after" means the Friday must be strictly
     AFTER the earnings date: an after-hours print lands once that day's
     options have already settled at the close, so a same-day Friday
     wouldn't actually be held through the event. For BMO, the same-day
     Friday still qualifies, since the print is out before that day's
     close. This wasn't a concern with the old "nearest 2 Fridays from
     today" logic (today is never earnings day for a ticker being newly
     entered), but matters now that selection is pinned to the earnings
     date itself.
"""
from datetime import date, timedelta


from paper_trading import (
    get_trading_client,
    get_option_data_client,
    get_latest_stock_price,
    get_latest_option_quote_mid,
)


def _quote_mid(q) -> float:
    bid, ask = float(q.bid_price), float(q.ask_price)
    if bid > 0 and ask > 0:
        return (bid + ask) / 2
    return ask or bid


def _batch_option_mids(symbols: list) -> dict:
    """Mid price for every symbol in `symbols`, fetched in ONE Alpaca call
    instead of one call per symbol -- see module docstring point 4."""
    if not symbols:
        return {}
    from alpaca.data.requests import OptionLatestQuoteRequest
    quote_client = get_option_data_client()
    quotes = quote_client.get_option_latest_quote(OptionLatestQuoteRequest(symbol_or_symbols=symbols))
    return {sym: _quote_mid(q) for sym, q in quotes.items()}


def _pick_otm_pair(contracts, spot_price):
    """From a list of contracts all at the same expiration, pick the
    nearest OTM call (strike >= spot) and nearest OTM put (strike <=
    spot), falling back to the nearest available contract on that side if
    none is OTM. Same bracketing convention used throughout this codebase
    (see paper_trading.find_atm_option_pair), verified there against real
    historical contracts. Returns None if either side is entirely missing.
    """
    calls = [c for c in contracts if c.type == "call"]
    puts = [c for c in contracts if c.type == "put"]
    if not calls or not puts:
        return None

    calls_otm = [c for c in calls if float(c.strike_price) >= spot_price]
    best_call = min(calls_otm, key=lambda c: float(c.strike_price)) if calls_otm \
        else max(calls, key=lambda c: float(c.strike_price))

    puts_otm = [c for c in puts if float(c.strike_price) <= spot_price]
    best_put = max(puts_otm, key=lambda c: float(c.strike_price)) if puts_otm \
        else min(puts, key=lambda c: float(c.strike_price))

    return best_call, best_put


def _earnings_threshold(er_date: date, er_time: str) -> date:
    """The earliest date whose Friday expiration would still be HELD
    THROUGH the earnings print -- see module docstring point 5. AMC needs
    a Friday strictly after er_date; BMO (or anything else) allows the
    same day, since the print is out before that day's options settle."""
    return er_date + timedelta(days=1) if er_time == "AMC" else er_date


def get_ranked_expirations(ticker: str, er_date: date, er_time: str,
                            num_expirations: int = 2, window_days: int = 45,
                            stock_price: float = None):
    """Returns up to `num_expirations` dicts ({straddle, expiration, dte})
    for `ticker`'s nearest distinct FRIDAY-listed expirations ON OR AFTER
    its earnings release -- index 0 is "a" (the expiration held through
    the print), index 1 is "b" (the next Friday after that). Friday-only
    (point 1) and earnings-anchored (point 5). `straddle` is already
    normalized by `ticker`'s own spot price (point 3). Raises if no
    Friday-expiration contracts are found at all within `window_days` of
    the earnings date; returns fewer than `num_expirations` entries if the
    ticker simply doesn't have that many distinct Friday expirations
    listed within the window.

    `er_date`/`er_time`: the ticker's own CONFIRMED next earnings date
    ("YYYY-MM-DD" or a date) and session ("BMO"/"AMC") -- callers should
    only reach this function once they have a confirmed date (point 5);
    passing an unconfirmed/estimated date would anchor the straddle to the
    wrong expiration.

    `stock_price`: pass this in if the caller already has a fresh quote
    (see module docstring point 4) to skip a redundant fetch here.
    """
    from alpaca.trading.requests import GetOptionContractsRequest

    if isinstance(er_date, str):
        er_date = date.fromisoformat(er_date)
    today = date.today()
    if stock_price is None:
        stock_price = get_latest_stock_price(ticker)
    client = get_trading_client()

    threshold = _earnings_threshold(er_date, er_time)

    contracts = []
    page_token = None
    for _ in range(20):  # same pagination cap used elsewhere for this API
        req = GetOptionContractsRequest(
            underlying_symbols=[ticker],
            expiration_date_gte=threshold.isoformat(),
            expiration_date_lte=(threshold + timedelta(days=window_days)).isoformat(),
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

    # Friday-only -- see module docstring point 1.
    contracts = [c for c in contracts if c.expiration_date.weekday() == 4]

    if not contracts:
        raise RuntimeError(
            f"No Friday-expiration option contracts found for {ticker} on/after "
            f"{threshold} (earnings {er_date} {er_time}) within {window_days} days"
        )

    exps = sorted({c.expiration_date for c in contracts})[:num_expirations]

    # Pick each expiration's OTM call/put pair first (no network calls),
    # then fetch every leg's quote in one batched request -- point 4.
    legs_by_exp = {}
    all_symbols = []
    for exp in exps:
        same_exp = [c for c in contracts if c.expiration_date == exp]
        pair = _pick_otm_pair(same_exp, stock_price)
        if pair is None:
            continue
        best_call, best_put = pair
        legs_by_exp[exp] = (best_call.symbol, best_put.symbol)
        all_symbols.append(best_call.symbol)
        all_symbols.append(best_put.symbol)

    mids = _batch_option_mids(all_symbols)

    results = []
    for exp in exps:
        if exp not in legs_by_exp:
            continue
        call_sym, put_sym = legs_by_exp[exp]
        if call_sym not in mids or put_sym not in mids:
            continue
        straddle_pct = (mids[call_sym] + mids[put_sym]) / stock_price
        results.append({"straddle": straddle_pct, "expiration": exp, "dte": (exp - today).days})

    return results


def get_straddle_at_expiration(symbol: str, expiration: date, _cache: dict = None) -> float:
    """Straddle (call mid + put mid), normalized by `symbol`'s own spot
    price (point 3), for `symbol` at one EXACT expiration date -- used to
    quote SPY at the ticker's own "a"/"b" dates rather than SPY's own
    independently-nearest expirations. See module docstring point 2.
    Raises if `symbol` has no listed contracts at that exact date.

    `_cache`: an optional caller-owned dict used to memoize (symbol,
    expiration) -> value across multiple calls. SPY is quoted at whatever
    Friday the ticker's own "a"/"b" legs land on, and most tickers on a
    given day share the same nearest one or two Fridays -- so across a
    batch of tickers (see main.py's /watchlist-live), SPY would otherwise
    be re-fetched for the same date dozens of times. Passing a shared dict
    turns that into (at most) a couple of real Alpaca calls per batch,
    which matters given Alpaca's 200-requests/minute account-wide cap
    (point 4).
    """
    if _cache is not None:
        key = (symbol, expiration)
        if key in _cache:
            return _cache[key]

    from alpaca.trading.requests import GetOptionContractsRequest

    spot_price = get_latest_stock_price(symbol)
    client = get_trading_client()

    contracts = []
    page_token = None
    for _ in range(20):
        req = GetOptionContractsRequest(
            underlying_symbols=[symbol],
            expiration_date=expiration.isoformat(),
            strike_price_gte=str(round(spot_price * 0.9, 2)),
            strike_price_lte=str(round(spot_price * 1.1, 2)),
            status="active",
            page_token=page_token,
        )
        resp = client.get_option_contracts(req)
        contracts.extend(resp.option_contracts)
        page_token = getattr(resp, "next_page_token", None)
        if not page_token:
            break

    if not contracts:
        raise RuntimeError(f"No option contracts found for {symbol} at expiration {expiration}")

    pair = _pick_otm_pair(contracts, spot_price)
    if pair is None:
        raise RuntimeError(f"No matching call/put pair for {symbol} at expiration {expiration}")

    best_call, best_put = pair
    mids = _batch_option_mids([best_call.symbol, best_put.symbol])
    if best_call.symbol not in mids or best_put.symbol not in mids:
        raise RuntimeError(f"No quote returned for {symbol} at expiration {expiration}")

    value = mids[best_call.symbol] + mids[best_put.symbol]
    value = value / spot_price

    if _cache is not None:
        _cache[(symbol, expiration)] = value
    return value


def get_live_straddle_inputs(ticker: str, er_date, er_time: str,
                              _spy_cache: dict = None, stock_price: float = None) -> dict:
    """Live equivalent of the old MOCK_LIVE[ticker] entry:
    {close_a, close_b, spy_close_a, spy_close_b} -- same shape
    get_straddle_percentile_live() already expects. `spy_close_a`/
    `spy_close_b` are SPY quoted at the SAME expiration dates as the
    ticker's own "a"/"b" legs (module docstring point 2), earnings-anchored
    (point 5). Raises if fewer than 2 distinct Friday expirations are
    available on/after the earnings date, or if SPY has no matching
    contract at either of those exact dates -- so callers can fall back to
    the historical (non-live) path cleanly.

    `er_date`/`er_time`: the ticker's own confirmed next earnings date and
    session -- required, see module docstring point 5.
    """
    ticker_legs = get_ranked_expirations(ticker.upper(), er_date, er_time, stock_price=stock_price)
    if len(ticker_legs) < 2:
        raise RuntimeError(
            f"Fewer than 2 Friday expirations found for {ticker} on/after earnings {er_date} {er_time}"
        )

    spy_close_a = get_straddle_at_expiration("SPY", ticker_legs[0]["expiration"], _cache=_spy_cache)
    spy_close_b = get_straddle_at_expiration("SPY", ticker_legs[1]["expiration"], _cache=_spy_cache)

    return {
        "close_a": ticker_legs[0]["straddle"],
        "close_b": ticker_legs[1]["straddle"],
        "spy_close_a": spy_close_a,
        "spy_close_b": spy_close_b,
    }
