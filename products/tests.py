

  
    # refresh from a logged-in SiteStripe session when amzn.to shortening fails

import os
import re
import asyncio
import aiohttp
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, unquote
from telegram import Update, Chat
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# =============================================================================
#  CONFIG
# =============================================================================
# Rotate this token in BotFather (it has been shared) and keep it in BOT_TOKEN.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7166438705:AAEzoZaT1vuDGheKR8DrhdE_r5sqD9yYv8o")

SITE_BASE = "https://dealhunts.in"
BOT_CONVERT_URL = f"{SITE_BASE}/api/bot-convert/"      # product mode (full fetch + save, server-side)
FALLBACK_SHORTENER_URL = f"{SITE_BASE}/api/shorten/"   # short mode

# ---------------------------------------------------------------------------
#  GROUP / USER -> affiliate tag
# ---------------------------------------------------------------------------
group_affiliate_tags = {
    "Affiliate bot": "ashfiyarajguru-21",
    "ASHFIYA KA BOT": "banalibanerjee-21",
    "POOJA AFFILIATE BOT": "alena01-21",
    "Rohin Affiliate Bot": "lootlobhai-21",
    "Swati Singh AFFILIATE BOT": "sehajdeepkaur-21",
    "Renuka Affiliate Bot": "282807-21",
    "Dabang affiliate bot": "dabangg00-21",
    "KULDEEP AFFILIATE BOT": "kuldeepsingh01-21",
    "Renuka Affiliate Bot 2": "priyanshgupta02-21",
    "Priyansh Affiliate Bot": "earnkaro0a7-21",
    "Naman Affiliate Bot": "saurabhrathore-21",
    "Kanika affiliate bot": "chandanmallah-21",
    "Madhukar Affiliate Bot": "indiantester01-21",
    "Arif Affiliate Bot": "cmar01-21",
    "Pooja Main Affiliate Bot": "harharmahadev0c-21",
    "Jaincy Affiliate Bot": "0c0-21",
    "Karishma Affiliate Bot": "brandinteger01-21",
    "Keyword Link": "keyword04-21",
    "Srashti Affiliate Bot": "sr0100-21",
}
user_affiliate_tags = {
    5765221170: "ashfiyarajguru-21",
}
DEFAULT_AFFILIATE_TAG = "alena01-21"

# Groups that get a SHORT link instead of a product page.
SHORT_LINK_GROUPS = {
    "Keyword Link",
    "Swati Singh AFFILIATE BOT",
    "Dabang affiliate bot"

}
SHORT_LINK_USERS = set()

# =============================================================================
#  Amazon native shortener (SHORT mode only)
# =============================================================================
AMAZON_MARKETPLACES = {
    "in": {"domain": "www.amazon.in", "marketplaceId": "44571"},
    "de": {"domain": "www.amazon.de", "marketplaceId": "A1PA6795UKMFR9"},
    "co.uk": {"domain": "www.amazon.co.uk", "marketplaceId": "A1F83G8C2ARO7P"},
}
DEFAULT_MARKETPLACE = AMAZON_MARKETPLACES["in"]
AMAZON_COOKIES = {
  "ubid-acbin": "262-4739513-0649807",
  "session-id": "260-8710822-1107321",
  "sid": "yLzpigbU/SDwIq5I6wwnIQ==|1SHCSTFUz8v6hZp8WFwk6TMf3MyEEZONf5szBnVafFQ=",
  "i18n-prefs": "INR",
  "sso-state-acbin": "Xdsso|ZQFXx7nZPSyFHZJjHlUMLCbqBu7vMJLxkNLumUej_rfRwhHnMjSl4Kv1vnm6gLOaw0QJp4V1wdrXHOEs4lTshBMUlgW25CeKW76Rs479wi2Y3LpV",
  "sst-acbin": "Sst1|PQIYu3cmYlEEstcavAkPq_FkCcXEY1EGCSwOArpwRvR1VabKwzv1UmAIuslKJs_tXc1gcKnQXoLE6BDvXvtDgFr_fsVDzjipyuHTwS8PipP5RFtypT2KcnkLXxdx7JfD3KClextwh9uchwps_JPDbJWTokyGm4DFK83XzEoxqMAafK6IeQVY-bAM3XgsZ5RwXl5nc-FHvI5nmgO28P8xlOHHUDuL5r3w2S4O1KazU9k4j-ZRVSjeUOs8JVv46wntkE8ziIk5bK8WgMtR6DpE_2UCs-HDDRIC4zo5O49P28VHr_k",
  "at-acbin": "Atza|gQDwvSnCAwEBAhLImEpw4h1XPd18zCBrZauLTr5nm0lv2a9er7y3HYruEqpNbbnLvCQ6juh-hoFbn72O-wMr0BmXW7RZemExxKbQUpyKTPJMlFfGrqlAfO-o8rdsMDSo8Hz_H9KfVyN85GQiGp5ImbJ5LFDveK7dX-gjXVKrWZ_QPFFpFK9AecIG6JL6KotZRqCqmDQ7T1LE5FKagIt-iK8el1kzKL48i--AOgU1CF2pcZ87qd-VkswKF7bvlhgiH8ftn8xdiwMqp1XAjydCJ0JaFp1oUNW9to1plVrkVfefaHSm9y2jEoy9flgb--RbQmEgYyuPaaGMh0L6hmKiuL4q83-rqkfb2sMgiEl2cAEzf_RpQIXNoaZq-736dWVeioXPtE-Ex2_GglMota8t40y576iwuRACO3qfKb7tD9xBeGbQDI1FBc0HxEWTi06hfTUhz20",
  "sess-at-acbin": "69fV/nTCIl94fZ0Glsb/tHmAfGnx97/BEGgYDGjK9es=",
  "lc-acbin": "en_IN",
  "session-id-time": "2082787201l",
  "session-token": "MI/sNj9R6WIF2USikpHHJRCkpWKtvcHCu/MHVPGjjt9vNHL1JYbeaeoUnCPeHfJzoQaXUgTGjA+QLpRJqEmYITZqR0LxWSruM37epVsueVdoNM357tu9tjU2XRXmarMAY28RJAbTpTGGjKNPS6Ii8Z5Q9ZrW10oN6ZQ49R1u8wc+a60RutG54Ff+F6IvmyKG59ZPlXt2Uk7yzTlF69u0Gzy0OjLbNoRZorj1lPgYw5YGgsDPPGvWDow9SbKE0gTy",
  "x-acbin": "llJzSJnW0WIvesXW5jv09MajNkmmImP7X7OAvqKe4@fIqfFW2uOhIbiJTHXV2ieK",
  "csm-hit": "tb:8BXWCZSRQAMKJZ4D76YJ+s-186XQ8CHASDD9SXY3A8N|1782144076802&t:1782144076802&adb:adblk_no",
  "rxc": "AEEasHGmvSlGaoG3xpg"
   # refresh from a logged-in SiteStripe session when amzn.to shortening fails
}
AMAZON_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"),
    "X-Requested-With": "XMLHttpRequest",
}

MAX_RETRIES = 5
RETRY_DELAY = 2
TIMEOUT = 15

session = None


# =============================================================================
#  HELPERS
# =============================================================================
async def init_session(application=None):
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession()
    return session


def normalize_url(url):
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def get_marketplace_from_url(url):
    try:
        hostname = urlparse(url).hostname or ""
        for value in AMAZON_MARKETPLACES.values():
            if hostname.endswith(value["domain"]):
                return value
    except Exception:
        pass
    return DEFAULT_MARKETPLACE


def extract_amazon_url_from_linkredirect(linkredirect_url):
    try:
        q = parse_qs(urlparse(linkredirect_url).query)
        if "dl" in q:
            return unquote(q["dl"][0])
    except Exception as e:
        print(f"linkredirect extract error: {e}")
    return linkredirect_url


async def expand_url(url, session, max_retries=MAX_RETRIES):
    for attempt in range(max_retries):
        try:
            url = normalize_url(url)
            async with session.get(url, allow_redirects=True, timeout=TIMEOUT) as r:
                expanded = str(r.url)
                if "linkredirect.in" in expanded:
                    return extract_amazon_url_from_linkredirect(expanded)
                return expanded
        except Exception as e:
            print(f"expand attempt {attempt + 1}/{max_retries} failed: {e}")
            if attempt < max_retries - 1:
                await asyncio.sleep(RETRY_DELAY)
    return url


def update_affiliate_tag(url, new_tag):
    url = normalize_url(url)
    p = urlparse(url)
    q = parse_qs(p.query, keep_blank_values=True)
    q["tag"] = [new_tag]
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q, doseq=True), ""))


SHORT_DOMAINS = ["amzn.in", "amzn.to", "amzn.eu", "bit.ly", "bitli.in",
                 "linkredirect.in", "amzn-to.co", "dealhunts.in"]


# =============================================================================
#  PRODUCT MODE -> /api/bot-convert/ (server runs convert_and_upsert: full
#  PA-API fetch, saves every field, dedups by ASIN). Returns product-page URL.
# =============================================================================
async def process_product(word, tag, session):
    try:
        async with session.post(BOT_CONVERT_URL, json={"url": word, "tag": tag},
                                timeout=120) as r:
            if r.status == 200:
                data = await r.json()
                if data.get("status") == "success" and data.get("product_url"):
                    return data["product_url"]
                print(f"bot-convert error: {data.get('error')}")
            else:
                body = (await r.text())[:200]
                print(f"bot-convert status {r.status}: {body}")
    except Exception as e:
        print(f"bot-convert error: {e}")

    # Fallback: still return a working tagged link if the API call failed.
    try:
        w = normalize_url(word)
        if any(d in w for d in SHORT_DOMAINS):
            w = await expand_url(w, session)
        return update_affiliate_tag(w, tag)
    except Exception:
        return word


# =============================================================================
#  SHORT-URL MODE
# =============================================================================
async def shorten_with_fallback_api(long_url, session):
    try:
        async with session.post(FALLBACK_SHORTENER_URL, json={"url": long_url},
                                timeout=TIMEOUT) as r:
            if r.status in (200, 201):
                d = await r.json()
                short = d.get("shortened_url") or d.get("short_url") or d.get("url")
                if short:
                    return short.replace("www.", "")
    except Exception as e:
        print(f"fallback shortener error: {e}")
    return long_url


async def get_amazon_short_url(long_url, session, marketplace_info):
    domain = marketplace_info.get("domain", "www.amazon.in")
    marketplace_id = marketplace_info.get("marketplaceId")
    if not marketplace_id:
        return None
    base = f"https://{domain}/associates/sitestripe/getShortUrl"
    params = {"longUrl": normalize_url(long_url), "marketplaceId": marketplace_id}
    headers = dict(AMAZON_HEADERS, Referer=f"https://{domain}/")
    try:
        async with session.get(base, params=params, headers=headers,
                               cookies=AMAZON_COOKIES, timeout=TIMEOUT) as r:
            if "/ap/signin" in str(r.url) or r.status == 401:
                return None
            if r.status == 200 and "text/html" not in r.headers.get("Content-Type", ""):
                d = await r.json()
                return d.get("shortUrl")
    except Exception as e:
        print(f"amazon shortener error: {e}")
    return None


async def make_short_link(final_url, session):
    mp = get_marketplace_from_url(final_url)
    if mp["domain"] == "www.amazon.in":
        amzn = await get_amazon_short_url(final_url, session, mp)
        if amzn:
            return amzn
    return await shorten_with_fallback_api(final_url, session)


async def process_short(word, tag, session):
    try:
        word = normalize_url(word)
        if any(d in word for d in SHORT_DOMAINS):
            word = await expand_url(word, session)
        final_url = update_affiliate_tag(word, tag)
        return await make_short_link(final_url, session) or final_url
    except Exception as e:
        print(f"process_short error: {e}")
        try:
            return update_affiliate_tag(word, tag)
        except Exception:
            return word


# =============================================================================
#  MESSAGE PARSING + DISPATCH
# =============================================================================
def find_urls_in_text(text):
    pattern = (r"(https?://[^\s]+|(?:www\.)?(?:amazon\.[a-z\.]{2,6}|amzn\.[a-z]{2}|"
               r"amzn-to\.co|bitli\.in|linkredirect\.in|dealhunts\.in)[^\s]*)")
    relevant = ["amazon.", "amzn.", "amzn-to.co", "bitli.in", "linkredirect.in", "dealhunts.in"]
    matches = []
    for m in re.finditer(pattern, text, re.IGNORECASE):
        url = m.group(0)
        if any(d in url.lower() for d in relevant):
            matches.append({"url": url, "start": m.start(), "end": m.end()})
    return matches


def resolve_tag_and_mode(chat, user_id):
    if chat.type in (Chat.GROUP, Chat.SUPERGROUP):
        name = chat.title
        tag = group_affiliate_tags.get(name, DEFAULT_AFFILIATE_TAG)
        mode = "short" if name in SHORT_LINK_GROUPS else "product"
    else:
        tag = user_affiliate_tags.get(user_id, DEFAULT_AFFILIATE_TAG)
        mode = "short" if user_id in SHORT_LINK_USERS else "product"
    return tag, mode


async def link_converter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message.text
    user_id = update.message.from_user.id
    chat = update.message.chat

    global session
    if session is None or session.closed:
        session = await init_session()

    tag, mode = resolve_tag_and_mode(chat, user_id)
    url_matches = find_urls_in_text(message)
    if not url_matches:
        return

    mode_label = "short link" if mode == "short" else "product page"
    processing = await update.message.reply_text(
        f"Processing {len(url_matches)} link(s) -> {mode_label}\n"
        f"Tag: {tag}\nFetching product details, please wait..."
    )

    replacements = []
    for i, m in enumerate(url_matches):
        if mode == "short":
            rep = await process_short(m["url"], tag, session)
        else:
            rep = await process_product(m["url"], tag, session)
        replacements.append(rep)
        if i < len(url_matches) - 1:
            await asyncio.sleep(0.4)

    modified = message
    for m, rep in sorted(zip(url_matches, replacements),
                         key=lambda x: x[0]["start"], reverse=True):
        modified = modified[:m["start"]] + rep + modified[m["end"]:]

    reply = f"Tag applied: {tag}\n\n{modified}"
    try:
        await processing.delete()
        await update.message.reply_text(reply, parse_mode=None)
    except Exception as e:
        print(f"reply error: {e}")
        await update.message.reply_text(reply)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "DealHunt Affiliate Bot\n\n"
        "Send Amazon links and I'll convert them.\n"
        "- Default groups: full product page created on dealhunts.in "
        "(price, MRP, discount, image, category - all fetched by the site).\n"
        "- Short-link groups: a short affiliate link instead."
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.message.chat
    user_id = update.message.from_user.id
    tag, mode = resolve_tag_and_mode(chat, user_id)
    where = f"Group: {chat.title}" if chat.type in (Chat.GROUP, Chat.SUPERGROUP) else f"User: {user_id}"
    await update.message.reply_text(
        f"Configuration\n\nTag: {tag}\n{where}\n"
        f"Mode: {'SHORT link' if mode == 'short' else 'PRODUCT page (full details)'}"
    )


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(MessageHandler(
        filters.TEXT & (filters.ChatType.GROUPS | filters.ChatType.PRIVATE),
        link_converter,
    ))
    app.post_init = init_session

    async def close_session(_app):
        global session
        if session and not session.closed:
            await session.close()

    app.post_shutdown = close_session

    print("=" * 60)
    print("DealHunt Affiliate Bot running")
    print(f"Site: {SITE_BASE}")
    print(f"Product endpoint: {BOT_CONVERT_URL}")
    print(f"Short-link groups: {sorted(SHORT_LINK_GROUPS) or '(none)'}")
    print("=" * 60)
    app.run_polling()


if __name__ == "__main__":
    main()