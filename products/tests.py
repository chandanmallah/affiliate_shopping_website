import sys
import re
import os
import asyncio
import aiohttp
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

FALLBACK_SHORTENER_URL = "https://dealhunts.in/api/shorten/"

# TARGET AFFILIATE TAG CONFIGURATION
TARGET_AFFILIATE_TAG = "sehajdeepkaur-21"
OUTPUT_FILE = "test.txt"

AMAZON_MARKETPLACES = {
    "in": {"domain": "www.amazon.in", "marketplaceId": "44571"},
}
DEFAULT_MARKETPLACE = AMAZON_MARKETPLACES["in"]

AMAZON_COOKIES = {
    "x-amz-captcha-1": "1758191185505360",
    "x-amz-captcha-2": "pJO5Z27LFTU+5QexwL7aUw==",
    "session-id": "523-9523293-8644603",
    "ubid-acbin": "525-8478998-7598650",
    "sid": '"4bwFaXLuq5047LuO9lh7CA==|3kCicvVZtCrI+0BU/ROrZ/cuMQsgoh1DKcflYCqK8bE="',
    "i18n-prefs": "INR",
    "lc-acbin": "en_IN",
    "rx": "AQB7Pi+Zry5rPFO5nTFwbrv/wag=@ARKvK2o=",
    "sso-state-acbin": "Xdsso|ZQF_IYWjEloHIgeJhLgFv9jO1UWUULnKtu-7kw2C432ckc01wHIBalHQsxv7pBErSsWr8nqqVCGCp4ub97H-Tm3JaP0arpozoFX99eYlfGFKm3SE",
    "at-acbin": "Atza|gQDp1ALfAwEBArlap7R3LXeCkZeJzCDLg4q147XmcAL0veqlZdRUYWKjsZWBNSW3mhdL-6GV24FUmNFs0X_Ks6nZQF2YlHcqKVI9w6VqL2zFsTuxnT1HOd-6w5N33rAmEp79ChyFxXpVnDfAlj8rQBxl3XQKLeJrRltUWSfM1eX7nQs6b_32HBLfH9MczcFz2KHYsDbRpShqNb20aK_ywsftJJLbxkQ1T3fr7Q2FM3wEO-vgrYISVfG2ri_TjVWEPWv3qhvGv5dfjK8Li5AAaMCHjxh-HVxlmcTv7nFaIy6U2O3qXiCtHtxXmiSNOFQUPQj2yQMutIfnDEaoFOg0qBWLWQSNxrYefwwplAhAH_5PrBjSNSTjGpM8ZTLDmdErVDecgNJIChnNTawXJrck3scwX9sL9PE-jZByWNm7xkz4jAmmULZzpd-MgQ6W-g",
    "sess-at-acbin": "7futdC8neRRCjq7wg/JbQjwcfAEgHLXfI1BQkl86G8Y=",
    "sst-acbin": "Sst1|PQI1HEN1IlHMvuyYh8ADXQnGDZPa25FNqTiMGVwTwRidknBsNQ0QWQw4zV5ETB9gtruSLIwXxCSb2iYDPhuAy1Y9SyEllEkrlcbMId-cC091A_mExHU0a5uADOF_geR8vSbxjSaAiANntKlIq2WjYSmYHI_rR3fvkglsep63jnW9NrrgwcZj9wkjoGI459a98_9xyrcNEYnI30xTXDtAI4jbbqfrUM-rvfD_CHP9kZUsgNOp3arEMYDg-zcTSlJGzZZ91_qe53-RVtfVs6D2asu7x3zovub83DknU4nZxQUxlJzKGRFB4jzEta3qlz0yZIZMMuzYUvuwEEF6KcQk4bd8f5atV4dmEIv6g5tyR9N6xdmD_ijjeYse26hUiOwb2Nyo",
    "x-acbin": '"6T@kqIylHZ73ulmATBtN5Sw2Arni?3GdZEDZ3UJzfeiwK3vf6qWHhQtxOnmc50sJ"',
    "session-token": "cYHY8im7emXDtoQXR39KJ65pMh98jo6g0SJqTfVQImOcpnm4RaOOnuPe46Q3mJrKqMOe814smG5560F1S8Mbd+GhrtBAFrvNOf3dUl+zqcpa8xzjdWNQXFF/Q7aAEBacM30pVKFxJb7v+Dp+BSgzpYRMbVhVljMGnNPn6dFXb6uAm7hxN/e70T+BJvZjvkG1MEWotuXM7T5FAQHJ3XJdVwjCQT/97bGJlfelZTMTBA2DbXuynYDxkkwSBFDLVP5g",
    "session-id-time": "2082787201l",
    "ak_bmsc": "1949F7241193F3014A3CDCD62C1ED120~000000000000000000000000000000~YAAQvfXSF7QO1cSeAQAAZ9hGygCYNZpgZbOoTeVlUJNSiBbljnAYR16FKBwbNRJ1kEY68IXHk5JSlkPxD4BEz4zqkik6d1juv+1gr7zevmorOQ6EXoiV/flD64xxiA4sfNNumh5/mmIrSSv0Fe2Yq+FEQGPZdA5mNmjjhjqY/p608tGDaWZV5n+xI3sZPNuIQYp4uf9tp2eQt12VJcteQ5uU7plCAWcEH8cYYlB26HBPBvk5WfH/RekuYwAiiONeVTxCy52xBRy3HpH5yQmVBDeg0tZohQQWX6gycyXR9L0tsY9Cp38BDmXojwVhGNlEv7JGzhHtpt3vSwDohb7bwOpyDg26SCATx9XsoCVbQIpfXzJfTG4HarRCIofmD8CfSueJdwzeHaG3yZhUdGMb0eDDVnyFyHMSog4VDrwj2nsjTUSlHEWDizIYiflq3F858QJb4wZb1hASHGhSRVdA7HP40wVqgTQU9ALc0GAeDd4x",
    "bm_sv": "C325C8BC96CF5206474CF3AD0CA7160D~YAAQvfXSFxJ/1cSeAQAA4TZHygAX/kCbVlji+Tam9wITSIk+eHePnQimfvtyqPa2pDuiICFV3znSDhJ2NFbQbKoMcwrCnJ/uCeNjyxbEm766snO5HXyl2PGfmUgsS/ohOVk87u0kLoxLD9mK9Dvh/GB/z81Ap/8qYWPe9ysasyCRZPIqwn7AjyqGdlU+NTw7RpnK9C2j148M7Zjxs3EVuTvx5mbZuad5+9nU8YKbdl6lS1iwCnU9+2fv+hsomtit~1",
    "rxc": "AAnWe6HTxOPUNmSZT+8"

}

AMAZON_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
}

# ============================================================================
# CORE CONVERSION UTILITIES
# ============================================================================

def normalize_url(url):
    url = url.strip()
    return url if url.startswith(('http://', 'https://')) else 'https://' + url

def clean_amazon_url(url):
    try:
        p = urlparse(url)
        q = parse_qs(p.query, keep_blank_values=True)
        if q.get('s') and any(v.lower() == 'bazaar' for v in q['s']):
            q.pop('s')
        return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q, doseq=True), ''))
    except Exception:
        return url

async def expand_url(url, sess):
    try:
        url = normalize_url(url)
        async with sess.get(url, allow_redirects=True, timeout=8) as r:
            exp = str(r.url)
            return clean_amazon_url(exp)
    except Exception:
        return url

def update_affiliate_tag(url, tag):
    url = clean_amazon_url(normalize_url(url))
    p = urlparse(url)
    q = parse_qs(p.query, keep_blank_values=True)
    q['tag'] = [tag]
    return urlunparse((p.scheme, p.netloc, p.path, p.params, urlencode(q, doseq=True), ''))

async def get_amazon_short_url(long_url, sess, mkt_info):
    domain = mkt_info.get("domain", "www.amazon.in")
    mid = mkt_info.get("marketplaceId")
    if not mid: return None
    base = f"https://{domain}/associates/sitestripe/getShortUrl"
    hdrs = {**AMAZON_HEADERS, "Referer": f"https://{domain}/"}
    try:
        async with sess.get(base, params={"longUrl": normalize_url(long_url), "marketplaceId": mid},
                             headers=hdrs, cookies=AMAZON_COOKIES, timeout=5) as r:
            if r.status == 200 and 'text/html' not in r.headers.get('Content-Type', ''):
                d = await r.json()
                return d.get("shortUrl")
    except Exception:
        pass
    return None

async def shorten_with_fallback_api(long_url, sess):
    try:
        async with sess.post(FALLBACK_SHORTENER_URL, json={"url": long_url}, timeout=5) as r:
            if r.status in [200, 201]:
                d = await r.json()
                s = d.get("shortened_url") or d.get("short_url") or d.get("url")
                if s: return s.replace("www.", "")
    except Exception:
        pass
    return None

async def process_single_url(url, sess):
    try:
        url = normalize_url(url)
        if any(d in url for d in ['amzn.in', 'amzn.to', 'bit.ly', 'linkredirect.in', 'dealhunts.in']):
            url = await expand_url(url, sess)
        
        long_url = update_affiliate_tag(url, TARGET_AFFILIATE_TAG)
        
        short = await get_amazon_short_url(long_url, sess, DEFAULT_MARKETPLACE)
        if not short:
            short = await shorten_with_fallback_api(long_url, sess)
            
        return short if short else long_url
    except Exception:
        return url

def find_urls_in_text(text):
    domains = ['amazon.', 'amzn.', 'amzn-to.co', 'bitli.in', 'linkredirect.in', 'dealhunts.in']
    spaced = re.sub(r'(?<=[^\s])(https?://)', r' \1', text)
    pat = r'(https?://[^\s]+|(?:www\.)?(?:amazon\.[a-z\.]{2,6}|amzn\.[a-z]{2}|amozn\.in|amzn-to\.co|bitli\.in|linkredirect\.in)[^\s]*)'
    return [{'url': m.group(0), 'start': m.start(), 'end': m.end()}
            for m in re.finditer(pat, spaced, re.IGNORECASE)
            if any(d in m.group(0).lower() for d in domains)]

# ============================================================================
# PROCESSING PIPELINE
# ============================================================================

async def process_text_block(message, sess):
    urls_to_process = find_urls_in_text(message)
    if not urls_to_process:
        return message

    print(f"\n[🔄] Converting {len(urls_to_process)} link(s) inline...")

    converted_urls = await asyncio.gather(*[
        process_single_url(m['url'], sess) for m in urls_to_process
    ])

    modified_message = message
    url_map = {m['url']: conv for m, conv in zip(urls_to_process, converted_urls)}
    
    for m in sorted(urls_to_process, key=lambda x: x['start'], reverse=True):
        modified_message = modified_message[:m['start']] + url_map[m['url']] + modified_message[m['end']:]

    return modified_message

# ============================================================================
# AUTOMATIC TERMINAL LOOP
# ============================================================================

async def main():
    print("=" * 65)
    print(f"⚡ AUTOMATIC BULK TO TEXT CONVERTER TERMINAL")
    print(f"📌 Active Tag: {TARGET_AFFILIATE_TAG}")
    print("=" * 65)
    print("💡 INSTRUCTIONS: Paste text chunk containing links and hit Enter.")
    print(f"   The updated text block will append directly into '{OUTPUT_FILE}'.")
    print("=" * 65)
    
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(limit=50, limit_per_host=15)) as session:
        while True:
            print("\n📥 Paste text below (Hit Enter on an empty line or type 'done' to process):")
            print("-" * 65)
            
            lines = []
            while True:
                try:
                    line = input()
                    if line.strip().lower() == 'done' or (not line.strip() and len(lines) > 0):
                        break
                    lines.append(line)
                except KeyboardInterrupt:
                    print("\n👋 Exiting terminal.")
                    return
                except EOFError:
                    break
            
            input_text = "\n".join(lines)
            if not input_text.strip():
                continue
                
            output_text = await process_text_block(input_text, session)
            cleaned_output = output_text.strip()

            # Append the output directly to test.txt
            try:
                with open(OUTPUT_FILE, "a", encoding="utf-8") as tf:
                    tf.write(cleaned_output + "\n\n" + "="*50 + "\n\n")
                print(f"✅ Successfully appended to text file -> '{OUTPUT_FILE}'")
            except Exception as txt_err:
                print(f"❌ Failed to write to file storage: {txt_err}")
            
            print("\n" + "=" * 25 + " CONVERTED OUTPUT " + "=" * 25)
            print(cleaned_output)
            print("=" * 68)

if __name__ == "__main__":
    asyncio.run(main())