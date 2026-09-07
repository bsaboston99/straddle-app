"""
Shared Web Push notification helpers.

Used by both the /alerts endpoints in main.py and the paper trading engine
(paper_trading.py), so a straddle alert and a paper trade (buy/sell) fire
push notifications through the exact same subscriber list and the exact
same pywebpush call -- one place to get this right instead of two copies
that could quietly drift apart.
"""
import os
import json
from pathlib import Path

VAPID_PUBLIC_KEY  = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_CLAIMS      = {"sub": "mailto:bsandersonn99@gmail.com"}

SUBSCRIPTIONS_FILE = Path(__file__).parent / "push_subscriptions.json"


def load_subscriptions() -> list:
    try:
        if SUBSCRIPTIONS_FILE.exists():
            return json.loads(SUBSCRIPTIONS_FILE.read_text())
    except Exception:
        pass
    return []


def save_subscriptions(subs: list):
    SUBSCRIPTIONS_FILE.write_text(json.dumps(subs))


def send_push(subscription: dict, title: str, body: str):
    """Send a single Web Push notification. Never raises -- a failed push
    (e.g. a stale/expired subscription) should never take down whatever
    real logic (an alert check, a trade) triggered it.
    """
    try:
        from pywebpush import webpush, WebPushException
        # Env vars lose real newlines -- restore them from literal \n
        private_key = VAPID_PRIVATE_KEY.replace("\\n", "\n")
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=private_key,
            vapid_claims=VAPID_CLAIMS,
        )
    except Exception as e:
        print(f"Push send error: {e}")


def send_push_to_all(title: str, body: str):
    """Push the same notification to every current subscriber."""
    for sub in load_subscriptions():
        send_push(sub, title=title, body=body)
