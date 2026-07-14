"""
test_webhook.py — test the TradingView webhook in views.py end-to-end.

Runs the REAL view in-process via Django's test client (no server needed) and
actually forwards to Telegram, so a success means your live setup will work too.

Run from your PROJECT ROOT (folder with manage.py):
    python test_webhook.py

It reads TV_WEBHOOK_SECRET from settings.py, then sends:
  1. a valid JSON signal      -> expect 200 "ok"  + message in Telegram
  2. a plain-text signal      -> expect 200 "ok"  + message in Telegram
  3. a wrong secret           -> expect 401 "unauthorized"
  4. a GET request            -> expect 200 "TradingView webhook is live."
"""

import os
import re
import sys
import json


def boot_django():
    sys.path.insert(0, os.getcwd())
    mod = os.environ.get("DJANGO_SETTINGS_MODULE")
    if not mod:
        try:
            with open("manage.py", encoding="utf-8") as f:
                m = re.search(r"DJANGO_SETTINGS_MODULE['\"]\s*,\s*['\"]([^'\"]+)['\"]", f.read())
            mod = m.group(1) if m else None
        except FileNotFoundError:
            mod = None
    if not mod:
        print("❌ Run from the folder with manage.py, or set DJANGO_SETTINGS_MODULE.")
        sys.exit(1)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", mod)
    import django
    django.setup()
    from django.conf import settings
    print(f"✅ Settings loaded: {mod}")
    return settings


def main():
    settings = boot_django()
    from django.test import Client

    secret = getattr(settings, "TV_WEBHOOK_SECRET", "")
    if not secret:
        print("❌ TV_WEBHOOK_SECRET is empty in settings.py — set it first.")
        return
    token = getattr(settings, "TV_TELEGRAM_BOT_TOKEN", "") or getattr(settings, "TELEGRAM_BOT_TOKEN", "")
    chat = getattr(settings, "TV_TELEGRAM_CHAT_ID", "") or getattr(settings, "TELEGRAM_CHAT_ID", "")
    print(f"Secret: {secret!r}   Telegram token set: {'yes' if token else 'NO'}   chat: {chat or '(none)'}")

    url = f"/api/tv-signal/{secret}/"
    bad_url = f"/api/tv-signal/wrong-secret/"
    c = Client()

    def show(name, resp, expect):
        body = resp.content.decode("utf-8", "ignore")[:120]
        ok = "✅" if resp.status_code == expect else "❌"
        print(f"{ok} {name}: HTTP {resp.status_code} (expected {expect})  body={body!r}")

    print("\n" + "=" * 55)
    print("WEBHOOK TESTS")
    print("=" * 55)

    # 1) valid JSON
    payload = {"ticker": "NIFTY", "action": "buy", "price": "22500",
               "sl": "22400", "tp": "22700", "interval": "5", "note": "test signal"}
    r1 = c.post(url, data=json.dumps(payload), content_type="application/json")
    show("valid JSON signal", r1, 200)

    # 2) plain text
    r2 = c.post(url, data="NIFTY BUY @ 22500 (auto test)",
                content_type="text/plain")
    show("plain-text signal", r2, 200)

    # 3) wrong secret
    r3 = c.post(bad_url, data=json.dumps(payload), content_type="application/json")
    show("wrong secret (should reject)", r3, 401)

    # 4) GET (health check)
    r4 = c.get(url)
    show("GET health check", r4, 200)

    print("\n" + "=" * 55)
    if not token or not chat:
        print("⚠️  Telegram token/chat not set — the view returns 200 but no message")
        print("    is delivered. Set TV_TELEGRAM_BOT_TOKEN / TV_TELEGRAM_CHAT_ID.")
    else:
        print("👉 Now check your Telegram chat — you should see TWO test signals")
        print("   (one formatted from JSON, one plain text).")
    print("=" * 55)


if __name__ == "__main__":
    main()