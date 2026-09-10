"""Entry point for the insignia-paper-trading Render cron job (see
render.yaml). Only actually pings insignia-api's /paper-trading/run-daily-check
during 9am-5pm ET.

The cron's own `schedule` field in render.yaml is a fixed UTC range, which
can't shift itself for the EST/EDT changeover -- so that schedule is
deliberately widened to cover BOTH offsets (an hour of slack on each end).
This script is what pins the real 9am-5pm ET boundary precisely, checked
freshly on every run via zoneinfo, so it stays correct year-round without
needing the render.yaml schedule touched again each time the clocks change.

Kept dependency-light on purpose (stdlib zoneinfo + requests only, no
pandas/alpaca-py) so the cron's own buildCommand can stay `pip install
requests` -- this process doesn't need the full backend-api environment,
it just fires one HTTP call at insignia-api, which does the real work
(and already no-ops itself off-hours/weekends via Alpaca's market clock in
paper_trading.run_daily_check -- this script just avoids spinning up a
cron run in the first place for the large majority of off-window minutes).
"""
from datetime import datetime
from zoneinfo import ZoneInfo

PAPER_TRADING_CHECK_URL = "https://insignia-api-qkex.onrender.com/paper-trading/run-daily-check"

now_et = datetime.now(ZoneInfo("America/New_York"))

if 9 <= now_et.hour < 17:
    import requests
    requests.post(PAPER_TRADING_CHECK_URL, timeout=30)
else:
    print(f"Outside 9am-5pm ET window (now {now_et.strftime('%H:%M')} ET) -- skipping.")
