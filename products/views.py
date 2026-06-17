from django.shortcuts import render, get_object_or_404, redirect
from django.core.cache import cache
from django.conf import settings
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt
from django.http import Http404

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view

# Note: Ensure you import AppConfiguration here
from .models import Product, ShortURL, AmazonLink, AppConfiguration
from .serializers import ProductSerializer

import json
import requests
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

# ─────────────────────────────────────────────────────────────
# DATABASE COOKIE STORAGE — Cloud & Stateless Compliant
# ─────────────────────────────────────────────────────────────

def load_cookies():
    """Load cookies from the database. Falls back to empty dict if missing."""
    try:
        config, _ = AppConfiguration.objects.get_or_create(key='amazon_cookies')
        return config.value
    except Exception as e:
        print(f"⚠️ Could not load cookies from database: {e}")
        return {}

def save_cookies(cookie_dict):
    """Persist updated cookies securely back into the database configuration record."""
    config, _ = AppConfiguration.objects.get_or_create(key='amazon_cookies')
    config.value = cookie_dict
    config.save()

AMAZON_HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/134.0.0.0 Safari/537.36"
    ),
    "X-Requested-With": "XMLHttpRequest",
    "Referer": "https://www.amazon.in/",
}

# ─────────────────────────────────────────────────────────────
# URL HELPERS
# ─────────────────────────────────────────────────────────────

def normalize_url(url):
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    return url

def clean_and_tag_url(url, tag):
    """Inject affiliate tag, strip junk tracking params."""
    parsed = urlparse(normalize_url(url))
    params = parse_qs(parsed.query, keep_blank_values=True)
    for junk in ['s', 'ref', 'psc', 'smid', 'th', 'ref_']:
        params.pop(junk, None)
    params['tag'] = [tag]
    return urlunparse((
        parsed.scheme, parsed.netloc, parsed.path,
        parsed.params, urlencode(params, doseq=True), ''
    ))


# ─────────────────────────────────────────────────────────────
# SHORTENING: AMZN.TO (Amazon SiteStripe) — PRIMARY
# ─────────────────────────────────────────────────────────────

def try_amazon_native_shorten(long_url):
    """
    Call Amazon SiteStripe getShortUrl API → amzn.to link.
    Prints a detailed failure reason to terminal if anything goes wrong.
    Returns short URL string on success, None on any failure.
    """
    print("\n" + "="*60)
    print("🔗 [AMZN.TO] Attempting Amazon native shortener")
    print(f"   URL: {long_url}")

    cookies = load_cookies()
    if not cookies:
        print("❌ [AMZN.TO] FAILED — Database configuration 'amazon_cookies' is empty or missing")
        print("   Fix: upload fresh cookies via the admin panel UI")
        print("="*60)
        return None

    print(f"   Cookies loaded from DB: {len(cookies)} keys → {list(cookies.keys())[:4]}…")

    api_url = "https://www.amazon.in/associates/sitestripe/getShortUrl"
    params  = {
        "longUrl":       normalize_url(long_url),
        "marketplaceId": "44571",   # amazon.in marketplace
    }

    print(f"   Calling: {api_url}")
    print(f"   Params:  {params}")

    try:
        resp = requests.get(
            api_url,
            params=params,
            headers=AMAZON_HEADERS,
            cookies=cookies,
            timeout=10,
            allow_redirects=True,
        )

        print(f"   HTTP status : {resp.status_code}")
        print(f"   Final URL   : {resp.url}")
        print(f"   Content-Type: {resp.headers.get('Content-Type', 'unknown')}")

        # ── Login redirect ──────────────────────────────────────
        if '/ap/signin' in resp.url:
            print("❌ [AMZN.TO] FAILED — Redirected to Amazon login page")
            print("   Reason: Cookies are EXPIRED or belong to wrong account")
            print("   Fix: Log into amazon.in Associates, copy fresh cookies, update via admin panel")
            print("="*60)
            return None

        if resp.status_code == 401:
            print("❌ [AMZN.TO] FAILED — HTTP 401 Unauthorized")
            print("   Reason: Amazon rejected the cookies (expired or invalid)")
            print("   Fix: Refresh cookies from amazon.in and update via admin panel")
            print("="*60)
            return None

        if resp.status_code == 403:
            print("❌ [AMZN.TO] FAILED — HTTP 403 Forbidden")
            print("   Reason: Account may not have Associates access, or IP is blocked")
            print("="*60)
            return None

        # ── HTML response (should be JSON) ──────────────────────
        ct = resp.headers.get('Content-Type', '')
        if 'text/html' in ct:
            snippet = resp.text[:400].replace('\n', ' ').strip()
            print("❌ [AMZN.TO] FAILED — Got HTML instead of JSON")
            print("   Reason: Almost certainly expired/invalid cookies (Amazon served login/error page)")
            print(f"   Response snippet: {snippet}")
            print("   Fix: Refresh cookies from amazon.in Associates SiteStripe toolbar")
            print("="*60)
            return None

        # ── Non-200 ─────────────────────────────────────────────
        if resp.status_code != 200:
            print(f"❌ [AMZN.TO] FAILED — Unexpected HTTP {resp.status_code}")
            print(f"   Response body: {resp.text[:300]}")
            print("="*60)
            return None

        # ── Parse JSON ──────────────────────────────────────────
        try:
            data = resp.json()
        except Exception as je:
            print(f"❌ [AMZN.TO] FAILED — Response is not valid JSON: {je}")
            print(f"   Raw response (first 400 chars): {resp.text[:400]}")
            print("="*60)
            return None

        print(f"   JSON response: {data}")

        is_ok     = data.get("isOk", False)
        short_url = (
            data.get("shortUrl")
            or data.get("short_url")
            or data.get("ShortUrl")
            or data.get("url")
        )

        if not is_ok:
            error_msg = data.get("error") or data.get("message") or data.get("errorMessage") or "unknown"
            print(f"❌ [AMZN.TO] FAILED — Amazon API returned isOk=false")
            print(f"   Error from Amazon: {error_msg}")
            print(f"   Full response: {data}")
            print("   Common reasons:")
            print("   • URL is not a valid amazon.in product URL")
            print("   • Cookies expired — refresh from Associates SiteStripe")
            print("   • Account not enrolled in Associates programme")
            print("="*60)
            return None

        if not short_url:
            print(f"❌ [AMZN.TO] FAILED — isOk=true but no shortUrl field in response")
            print(f"   Full response keys: {list(data.keys())}")
            print(f"   Full response: {data}")
            print("="*60)
            return None

        # ── Success ─────────────────────────────────────────────
        short_url = short_url.replace("www.", "").strip()
        print(f"✅ [AMZN.TO] SUCCESS → {short_url}")
        print("="*60)
        return short_url

    except requests.exceptions.Timeout:
        print("❌ [AMZN.TO] FAILED — Request timed out after 10s")
        print("   Reason: Amazon API did not respond in time")
        print("="*60)
        return None

    except requests.exceptions.ConnectionError as ce:
        print(f"❌ [AMZN.TO] FAILED — Connection error: {ce}")
        print("   Reason: Could not reach amazon.in (network/DNS issue on server)")
        print("="*60)
        return None

    except Exception as e:
        print(f"❌ [AMZN.TO] FAILED — Unexpected exception: {type(e).__name__}: {e}")
        print("="*60)
        return None


# ─────────────────────────────────────────────────────────────
# SHORTENING: AMOZN.IN (our DB) — FALLBACK
# ─────────────────────────────────────────────────────────────

def shorten_with_amozn(long_url):
    """
    Store in our ShortURL model → returns amozn.in/<code> URL.
    Always succeeds as long as the DB is up.
    """
    obj, _ = ShortURL.objects.get_or_create(long_url=long_url)
    cache.set(f"short_url:{obj.short_code}", obj.long_url, timeout=86400)
    print(f"✅ Fallback amozn.in shortener: {obj.short_url}")
    return obj.short_url


# ─────────────────────────────────────────────────────────────
# COMBINED SHORTENER — tries amzn.to first, amozn.in second
# ─────────────────────────────────────────────────────────────

def shorten_url(long_url):
    """
    1. Try Amazon SiteStripe → amzn.to/XXXXXXX
    2. Fall back to our own DB → amozn.in/XXXXXXX
    Returns (short_url, method_used)
    """
    amzn_short = try_amazon_native_shorten(long_url)
    if amzn_short:
        return amzn_short, "amzn.to"

    fallback = shorten_with_amozn(long_url)
    return fallback, "amozn.in"


# ==========================================
# 1. HTML PAGE VIEWS
# ==========================================

def add_product_page(request):
    return render(request, 'products/add_product.html')


def product_list(request):
    products_list = Product.objects.select_related('link').all().order_by('-created_at')
    paginator = Paginator(products_list, 8)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'products/product_cards_partial.html', {'page_obj': page_obj})

    return render(request, 'products/product_list.html', {'page_obj': page_obj})


def product_detail(request, slug):
    product = get_object_or_404(Product, link__slug=slug)
    return render(request, 'products/product_detail.html', {'product': product})


# ==========================================
# 2. REDIRECT ENGINE
# ==========================================

RESERVED_PATHS = {
    'api', 'admin', 'product', 'add-product',
    'static', 'media', 'favicon.ico', 'robots.txt',
}

def redirect_short(request, code):
    if code in RESERVED_PATHS or len(code) > 20 or '=' in code:
        raise Http404("Not found")

    cache_key = f"short_url:{code}"
    long_url = cache.get(cache_key)

    if not long_url:
        entry = get_object_or_404(ShortURL, short_code=code)
        long_url = entry.long_url
        cache.set(cache_key, long_url, timeout=86400)

    return redirect(long_url)


def redirect_short_url(request, shortcode):
    return redirect_short(request, code=shortcode)


# ==========================================
# 3. API — PRODUCTS
# ==========================================

class ProductListCreateAPIView(APIView):
    def get(self, request):
        products = Product.objects.select_related('link').all()
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            product = serializer.save()
            return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ==========================================
# 4. API — SHORTEN  (amzn.to first, amozn.in fallback)
# ==========================================

@csrf_exempt
@api_view(["POST"])
def create_short_url(request):
    """
    POST /api/shorten/
    Body: { "url": "<amazon url>", "tag": "<affiliate tag>" }
    """
    raw_url = request.data.get("url", "").strip()
    tag     = request.data.get("tag", "kuldeepsingh01-21").strip()

    if not raw_url:
        return Response({"error": "url is required"}, status=400)
    if not tag:
        return Response({"error": "tag is required"}, status=400)

    long_url = clean_and_tag_url(raw_url, tag)
    print(f"📎 Tagged URL: {long_url}")

    short_url, method = shorten_url(long_url)
    print(f"🔗 Final short URL [{method}]: {short_url}")

    short_code = short_url.rstrip('/').split('/')[-1]

    return Response({
        "long_url":   long_url,
        "short_url":  short_url,
        "short_code": short_code,
        "method":     method,
    })


# ==========================================
# 5. API — UPDATE COOKIES 
# ==========================================

@csrf_exempt
@api_view(["POST"])
def update_amazon_cookies(request):
    """
    POST /api/cookies/update/
    Body: { "session-id": "...", "at-acbin": "...", ... }
    Merges records directly into the operational database.
    """
    new_cookies = request.data
    if not new_cookies or not isinstance(new_cookies, dict):
        return Response({"error": "Send a JSON dict of cookie key→value pairs"}, status=400)

    current = load_cookies()
    for key, val in new_cookies.items():
        if key in ["sid", "x-acbin"] and val and not str(val).startswith('"'):
            current[key] = f'"{val}"'
        else:
            current[key] = val

    save_cookies(current)

    return Response({
        "message": "Cookies successfully synchronized and saved directly to database space.",
        "total_keys": len(current),
        "updated_keys": list(new_cookies.keys())
    })