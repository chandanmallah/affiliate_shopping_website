"""
test.py — test the LIVE TradingView webhook on dealhunts.in over HTTP.

Just run it (no Django, no server needed):
    python test.py

It POSTs sample signals to your deployed webhook and checks the responses,
then you confirm the messages arrived in Telegram.
"""

import json
import urllib.request
import urllib.error

# ── Your live webhook URL (with the secret) ──────────────────────────────────
WEBHOOK_URL = "https://dealhunts.in/api/tv-signal/chandan28maihutu/"
# ─────────────────────────────────────────────────────────────────────────────

# a deliberately-wrong-secret URL, for the rejection test
_base = WEBHOOK_URL.rstrip("/").rsplit("/", 1)[0]      # .../api/tv-signal
BAD_URL = _base + "/wrong-secret-xyz/"


def post(url, body, content_type):
    data = body.encode() if isinstance(body, str) else body
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": content_type}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, str(e)


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=25) as r:
            return r.status, r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "ignore")
    except Exception as e:
        return None, str(e)


def show(name, status, body, expect):
    ok = "✅" if status == expect else "❌"
    print(f"{ok} {name}: HTTP {status} (expected {expect})  body={body[:120]!r}")


def main():
    print("=" * 60)
    print("LIVE WEBHOOK TEST")
    print(f"URL: {WEBHOOK_URL}")
    print("=" * 60)

    # 1) valid JSON signal
    payload = json.dumps({
        "ticker": "NIFTY", "action": "buy", "price": "22500",
        "sl": "22400", "tp": "22700", "interval": "5", "note": "live test signal",
    })
    s, b = post(WEBHOOK_URL, payload, "application/json")
    show("valid JSON signal", s, b, 200)

    # 2) plain-text signal
    s, b = post(WEBHOOK_URL, "NIFTY BUY @ 22500 (auto text live test)", "text/plain")
    show("plain-text signal", s, b, 200)

    # 3) wrong secret -> should be rejected
    s, b = post(BAD_URL, payload, "application/json")
    show("wrong secret (should reject)", s, b, 401)

    # 4) GET health check
    s, b = get(WEBHOOK_URL)
    show("GET health check", s, b, 200)

    print("=" * 60)
    print("👉 Now check your Telegram chat — you should see TWO signals")
    print("   (one formatted from JSON, one plain text).")
    print("   If tests pass but nothing arrives, the Telegram token/chat id")
    print("   in settings.py are wrong — the webhook returns 200 either way.")
    print("=" * 60)


if __name__ == "__main__":
    main()