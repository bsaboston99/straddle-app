"""
Live options-quote helpers for the Earnings/Analysis screens and the
existing alerts feature -- replaces the old hardcoded MOCK_LIVE dict in
main.py with real Alpaca data.

This matches the ACTUAL historical construction in
Reverse Theta/Code/parquetcombine.py, confirmed by reading that script
directly rather than guessing from output patterns. Two rules matter here,
both confirmed against the source and against real historical data rather
than assumed:

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
   NVDA and the rest of this app's watchlist all qualify). Left unfiltered,
   a live "nearest 2 expirations" query today could return, say, next
   Monday and next Wednesday -- a 2-day gap the historical percentile
   buckets were never built to represent, since that cadence didn't exist
   when the training data was constructed. Filtering live selection to
   Friday-only expirations reproduces the cadence the model actually saw.

2. SPY is NOT independently ranked -- it is quoted at the TICKER'S OWN
   expiration dates.
   Confirmed by reading parquetcombine.py's SPY-merge block: it joins SPY's
   call/put quotes onto each row using `option_expiration_y` /
   `option_expirationa_y` -- i.e. the ticker's own selected "a"/"b"
   expiration dates -- not a separately-computed "SPY's nearest 2
   expirations." (`spy_c_exp_diff = option_exp_diff_x` makes this explicit:
   SPY's DTE is defined to equal the ticker's DTE, because it's the same
   date.) This matters because SPY has had daily-expiring listed options
   since 2022; independently ranking SPY's own nearest 2 expirations would
   almost always pick a far tighter, unrelated pair of dates than the
   ticker's own (Friday-spaced) pair -- comparing the ticker's straddle
   against the wrong SPY maturity entirely. The correct read of
   rel_straddle_a is "ticker's front-month straddle vs. what SPY's straddle
   costs at that SAME calendar expiration" -- a same-maturity comparison,
   not two independently-chosen tenors.

3. Every straddle value is normalized by ITS OWN underlying's spot price,
   not a raw dollar mid-price.
   Confirmed by reading parquetcombine.py's derived-column block:
   `closestraddle_a = (callclose_a + putclose_a) / stock_close` and
   `closespystraddle_a = (spycallclose_a + spyputclose_a) / spy_close` --
   i.e. the ticker's straddle is divided by the TICKER's price, and SPY's
   straddle is divided by SPY's OWN price (not the ticker's). Passing raw
   dollar mid-prices instead (an earlier version of this file did exactly
   that) silently changes the scale of every number fed into
   get_straddle_percentile_live, since rel_straddle_a is really comparing
   two already-normalized percentages, not two dollar figures.
"""
from datetime import date, timedelta


from paper_trading import (
    get_trading_client,
    get_latest_stock_price,
    get_latest_option_quote_mid,
)


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


def get_ranked_expirations(ticker: str, num_expirations: int = 2, window_days: int = 60):
    """Returns up to `num_expirations` dicts ({straddle, expiration, dte})
    for `ticker`'s nearest distinct FRIDAY-listed expirations, ranked
    ascending by DTE -- index 0 is "a" (front month), index 1 is "b" (back
    month). Friday-only, see module docstring point 1. Raises if no
    Friday-expiration contracts are found at all within `window_days`;
    returns fewer than `num_expirations` entries if the ticker simply
    doesn't have that many distinct Friday expirations listed within the
    window.
    """
    from alpaca.trading.requests import GetOptionContractsRequest

    today = date.today()
    stock_price = get_latest_stock_price(ticker)
    client = get_trading_client()

    contracts = []
    page_token = None
    for _ in range(20):  # same pagination cap used elsewhere for this API
        req = GetOptionContractsRequest(
            underlying_symbols=[ticker],
            expiration_date_gte=today.isoformat(),
            expiration_date_lte=(today + timedelta(days=window_days)).isoformat(),
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
        raise RuntimeError(f"No Friday-expiration option contracts found for {ticker} within {window_days} days")

    exps = sorted({c.expiration_date for c in contracts})[:num_expirations]

    results = []
    for exp in exps:
        same_exp = [c for c in contracts if c.expiration_date == exp]
        pair = _pick_otm_pair(same_exp, stock_price)
        if pair is None:
            continue
        best_call, best_put = pair
        call_px = get_latest_option_quote_mid(best_call.symbol)
        put_px = get_latest_option_quote_mid(best_put.symbol)
        # Normalized by the ticker's own spot price -- see module docstring point 3.
        straddle_pct = (call_px + put_px) / stock_price
        results.append({"straddle": straddle_pct, "expiration": exp, "dte": (exp - today).days})

    return results


def get_straddle_at_expiration(symbol: str, expiration: date) -> float:
    """Straddle (call mid + put mid) for `symbol` at one EXACT expiration
    date -- used to quote SPY at the ticker's own "a"/"b" dates rather than
    SPY's own independently-nearest expirations. See module docstring
    point 2. Raises if `symbol` has no listed contracts at that exact date.
    """
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
    call_px = get_latest_option_quote_mid(best_call.symbol)
    put_px = get_latest_option_quote_mid(best_put.symbol)
    # Normalized by this symbol's own spot price -- see module docstring point 3.
    return (call_px + put_px) / spot_price


def get_live_straddle_inputs(ticker: str) -> dict:
    """Live equivalent of the old MOCK_LIVE[ticker] entry:
    {close_a, close_b, spy_close_a, spy_close_b} -- same shape
    get_straddle_percentile_live() already expects. `spy_close_a`/
    `spy_close_b` are SPY quoted at the SAME expiration dates as the
    ticker's own "a"/"b" legs (module docstring point 2), not SPY's own
    nearest expirations. Raises if fewer than 2 distinct Friday
    expirations are available for the ticker, or if SPY has no matching
    contract at either of those exact dates -- so callers can fall back to
    the historical (non-live) path cleanly.
    """
    ticker_legs = get_ranked_expirations(ticker.upper())
    if len(ticker_legs) < 2:
        raise RuntimeError(f"Fewer than 2 Friday expirations found for {ticker}")

    spy_close_a = get_straddle_at_expiration("SPY", ticker_legs[0]["expiration"])
    spy_close_b = get_straddle_at_expiration("SPY", ticker_legs[1]["expiration"])

    return {
        "close_a": ticker_legs[0]["straddle"],
        "close_b": ticker_legs[1]["straddle"],
        "spy_close_a": spy_close_a,
        "spy_close_b": spy_close_b,
    }
