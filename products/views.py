from django.shortcuts import render, get_object_or_404, redirect
from django.core.cache import cache
from django.conf import settings
from django.core.paginator import Paginator
from django.views.decorators.csrf import csrf_exempt, ensure_csrf_cookie
from django.http import Http404, HttpResponse
from django.db import transaction
from django.db.models import Max, Q, F
from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.core.mail import send_mail

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.permissions import IsAuthenticated  # Optional: for admin protection

# Note: Ensure you import AppConfiguration here
from .models import Product, ShortURL, AmazonLink, AppConfiguration, ProductSnapshot
from .serializers import ProductSerializer
from .forms import ContactForm

import json
import re
import requests
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from creatorsapi_python_sdk.api_client import ApiClient
from creatorsapi_python_sdk.api.default_api import DefaultApi
from creatorsapi_python_sdk.models.get_items_request_content import GetItemsRequestContent
from creatorsapi_python_sdk.exceptions import ApiException

# ─────────────────────────────────────────────────────────────
# DATABASE COOKIE STORAGE — Cloud & Stateless Compliant
# ─────────────────────────────────────────────────────────────

AMAZON_API_CONFIG = {
    "CREDENTIAL_ID": "4v6br6lho9jsi7mc1iu418ci5c",
    "CREDENTIAL_SECRET": "1oga06qok3g9nd2r92ogl5aqpe9b7kumr34e1aolceecdlfpgtnv",
    "VERSION": "2.2",
    "MARKETPLACE": "www.amazon.in",
}


# ─────────────────────────────────────────────────────────────
# CORE SDK FETCH FUNCTION
# ─────────────────────────────────────────────────────────────
def fetch_product_from_creators_api(asin, partner_tag):
    """
    Directly initializes the Creators API SDK and requests item details.
    Extracts core fields, nested money metrics, and complete browse node category hierarchies.
    """
    try:
        # Initialize the API Client
        api_client = ApiClient(
            credential_id=AMAZON_API_CONFIG["CREDENTIAL_ID"],
            credential_secret=AMAZON_API_CONFIG["CREDENTIAL_SECRET"],
            version=AMAZON_API_CONFIG["VERSION"]
        )
        api = DefaultApi(api_client)

        # Define the structural resources to grab from Amazon
        resources = [
            'images.primary.large', 'images.primary.medium',
            'images.variants.large', 'images.variants.medium',
            'itemInfo.title', 'itemInfo.features',
            'offersV2.listings.price',
            'browseNodeInfo.browseNodes',                # Required for categories
            'browseNodeInfo.browseNodes.ancestor',       # Required for paths
            'browseNodeInfo.browseNodes.salesRank',      # Required for category ranks
            'browseNodeInfo.websiteSalesRank',           # Required for overall site rank
        ]
        
        req = GetItemsRequestContent(partner_tag=partner_tag, item_ids=[asin], resources=resources)
        response = api.get_items(x_marketplace=AMAZON_API_CONFIG["MARKETPLACE"], get_items_request_content=req)

        if not response.items_result or not response.items_result.items:
            return None

        item = response.items_result.items[0]
        
        # Initialize schema mapping with strict defaults
        data = {
            "title": "Amazon Product",
            "primary_image": "",
            "all_images": [],
            "price": "Check on Amazon",
            "price_amount": None,
            "price_currency": "INR",
            "mrp_amount": None,
            "mrp_display": "",
            "discount_percentage": None,
            "savings_amount": None,
            "savings_display": "",
            "features": [],
            "overall_rank": None,
            "overall_rank_context": "",
            "category_rankings": []                     # Will match JSONField requirements
        }

        # Extract Title
        if item.item_info and item.item_info.title:
            t = item.item_info.title
            data["title"] = t.display_value if hasattr(t, 'display_value') else str(t)

        # Extract Primary and Variant Images
        if item.images:
            if item.images.primary:
                for sz in ['large', 'medium']:
                    obj = getattr(item.images.primary, sz, None)
                    if obj and hasattr(obj, 'url'):
                        data["primary_image"] = obj.url
                        data["all_images"].append(obj.url)
                        break
            
            if hasattr(item.images, 'variants') and item.images.variants:
                for v in item.images.variants:
                    for sz in ['large', 'medium']:
                        obj = getattr(v, sz, None)
                        if obj and hasattr(obj, 'url'):
                            if obj.url not in data["all_images"]:
                                data["all_images"].append(obj.url)
                            break

        # ---- EXTRACT NESTED PRICING METRICS VIA MONEY OBJECTS ----
        if item.offers_v2 and item.offers_v2.listings:
            for listing in item.offers_v2.listings:
                price_obj = getattr(listing, "price", None)
                if price_obj:
                    money_obj = getattr(price_obj, "money", None)
                    if money_obj:
                        if hasattr(money_obj, 'display_amount'):
                            data["price"] = money_obj.display_amount  #
                        if hasattr(money_obj, 'amount'):
                            data["price_amount"] = money_obj.amount    #
                        if hasattr(money_obj, 'currency'):
                            data["price_currency"] = money_obj.currency  #

                    savings_obj = getattr(price_obj, "savings", None)
                    if savings_obj:
                        if hasattr(savings_obj, 'percentage'):
                            data["discount_percentage"] = savings_obj.percentage #
                        
                        sav_money = getattr(savings_obj, "money", None)
                        if sav_money:
                            if hasattr(sav_money, 'display_amount'):
                                data["savings_display"] = sav_money.display_amount #
                            if hasattr(sav_money, 'amount'):
                                data["savings_amount"] = sav_money.amount

                    sb_obj = getattr(price_obj, "saving_basis", None)
                    if sb_obj:
                        sb_money = getattr(sb_obj, "money", None)
                        if sb_money:
                            if hasattr(sb_money, 'display_amount'):
                                data["mrp_display"] = sb_money.display_amount #
                            if hasattr(sb_money, 'amount'):
                                data["mrp_amount"] = sb_money.amount          #
                break

        # ---- EXTRACT CATEGORY AND RANKINGS DATA ----
        bni = getattr(item, "browse_node_info", None)
        if bni:
            # 1. Overall Website Rank
            wsr = getattr(bni, "website_sales_rank", None)
            if wsr:
                if hasattr(wsr, 'sales_rank'):
                    data["overall_rank"] = wsr.sales_rank
                ctx = getattr(wsr, "context_free_name", None) or getattr(wsr, "display_name", None)
                if ctx:
                    data["overall_rank_context"] = str(ctx)

            # 2. Specific Browse Nodes Category List
            nodes = getattr(bni, "browse_nodes", None)
            if nodes:
                for n in nodes:
                    # Filter nodes that have a valid sales rank assigned
                    rank = getattr(n, "sales_rank", None)
                    if rank:
                        name = getattr(n, "context_free_name", None) or getattr(n, "display_name", "Unknown")
                        node_id = getattr(n, "id", "")
                        is_root = getattr(n, "is_root", False)
                        
                        # Trace backward ancestor list path hierarchy
                        anc = getattr(n, "ancestor", None)
                        chain = []
                        while anc:
                            aname = getattr(anc, "context_free_name", None) or getattr(anc, "display_name", "")
                            if aname:
                                chain.append(aname)
                            anc = getattr(anc, "ancestor", None)
                        
                        # Construct breadcrumb string format matching your logs
                        full_path = ""
                        if chain:
                            full_path = " > ".join(reversed(chain)) + f" > {name}"
                        else:
                            full_path = str(name)
                        
                        # Add tracking item payload properties mapped onto Model specification
                        data["category_rankings"].append({
                            "node_id": str(node_id),
                            "name": str(name),
                            "rank": int(rank),
                            "is_root": bool(is_root),
                            "path": full_path
                        })

        # Extract Feature Bullets
        if item.item_info and item.item_info.features:
            if hasattr(item.item_info.features, 'display_values'):
                for f in item.item_info.features.display_values[:4]:
                    val = f.display_value if hasattr(f, 'display_value') else str(f)
                    data["features"].append(val)

        return data

    except ApiException as ae:
        print(f"❌ [Creators API Exception] ASIN={asin}: {ae}")
        return None
    except Exception as e:
        print(f"❌ [Unexpected API Error] ASIN={asin}: {e}")
        return None
       
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

def is_search_link(url):
    """True for Amazon keyword/search links (.../s?k=...). These should stay
    search links (a full listing), not be converted into a single product."""
    try:
        p = urlparse(normalize_url(url))
        path = (p.path or "").rstrip("/").lower()
        q = parse_qs(p.query)
        return path == "/s" and ("k" in q or "keywords" in q)
    except Exception:
        return False


def clean_search_url(url, tag):
    """Keep only the search keyword + affiliate tag (drop hidden-keywords and
    all tracking junk) so the link opens the full search results page."""
    p = urlparse(normalize_url(url))
    q = parse_qs(p.query, keep_blank_values=True)
    kw = (q.get("k") or q.get("keywords") or [""])[0]
    netloc = p.netloc or "www.amazon.in"
    new_q = {"k": kw, "tag": tag}
    return urlunparse((p.scheme or "https", netloc, "/s", "",
                       urlencode(new_q), ""))


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
    Our own reliable shortener -> https://dealhunts.in/<code>.
    Always returns a real short link (never the long URL) while the DB is up.
    """
    return shorten_with_amozn(long_url), "dealhunts.in"


# ==========================================
# 1. HTML PAGE VIEWS
# ==========================================

# ─────────────────────────────────────────────────────────────
# CATALOG / CATEGORY HELPERS
# ─────────────────────────────────────────────────────────────

# The fixed category strip shown on the homepage. Clicking a tab filters
# by these labels (matched case-insensitively against Product.category).
STRIP_CATEGORIES = [
    "Amazon Devices", "Appliances", "Apps & Games", "Baby", "Beauty",
    "Bags, Wallets & Luggage", "Books", "Car & Motorbike", "Clothing & Accessories",
    "Collectibles", "Computers & Accessories", "Deals", "Electronics",
    "Furniture", "Garden & Outdoors", "Gift Cards", "Grocery & Gourmet Foods",
    "Health & Personal Care", "Home & Kitchen", "Home Improvement",
    "Industrial & Scientific", "Jewellery", "Kindle Store", "Movies & TV Shows",
    "Music", "Musical Instruments", "Office Products", "Pet Supplies",
    "Shoes & Handbags", "Software", "Sports, Fitness & Outdoors",
    "Tools & Home Improvement", "Toys & Games", "Video Games", "Watches",
]

NON_AMAZON_SOURCES = ["flipkart", "myntra", "ajio"]

PAGE_SIZE = 48           # cards per page (full "see all" / category views)
HOMEPAGE_SHOW = 24         # Amazon cards shown on the homepage before "See all"
HOMEPAGE_MAX = 120         # max Amazon cards cached for the homepage
TRENDING_LIMIT = 12        # max cards in each marketplace section on the homepage
CATEGORY_PAGE_SIZE = PAGE_SIZE


def derive_amazon_category(product_data):
    """
    Pick a single normalized DEPARTMENT label for an Amazon product, suitable
    for the homepage category strip (e.g. "Computers & Accessories").

    Order of preference:
      1. An explicit is_root browse node's name.
      2. The first segment of the longest breadcrumb path (the department),
         e.g. "Computers & Accessories > ... > Laptop Backpacks" -> "Computers & Accessories".
      3. The first ranking's name (last-resort leaf fallback).
    """
    rankings = product_data.get("category_rankings") or []

    root = next((r for r in rankings if r.get("is_root") and r.get("name")), None)
    if root:
        return root["name"].strip()

    best_path = ""
    for r in rankings:
        p = (r.get("path") or "")
        if len(p) > len(best_path):
            best_path = p
    if best_path:
        return best_path.split(" > ")[0].strip()

    if rankings and rankings[0].get("name"):
        return rankings[0]["name"].strip()
    return ""


def build_product_queryset(category=None, source=None, sources=None):
    """
    Returns a paginatable Product queryset with Amazon entries de-duplicated
    by ASIN (one row per ASIN, keeping the most recently created). Non-Amazon
    products and any Amazon rows without an ASIN are always kept as-is.

    Optional filters:
      - category : case-insensitive match against Product.category
      - source   : single source string ("amazon"/"flipkart"/...)
      - sources  : list of source strings
    """
    qs = Product.objects.select_related("link")
    if source:
        qs = qs.filter(source=source)
    if sources:
        qs = qs.filter(source__in=sources)
    if category:
        qs = qs.filter(category__icontains=category)

    amazon = qs.filter(source="amazon").exclude(
        Q(link__asin__isnull=True) | Q(link__asin="")
    )
    amazon_ids = list(
        amazon.values("link__asin").annotate(mid=Max("id")).values_list("mid", flat=True)
    )
    # Everything that is NOT an Amazon-with-ASIN row (non-Amazon + Amazon w/o ASIN)
    other_ids = list(
        qs.exclude(id__in=list(amazon.values_list("id", flat=True))).values_list("id", flat=True)
    )

    return (
        Product.objects.select_related("link")
        .filter(id__in=amazon_ids + other_ids)
        .order_by("-created_at")
    )


# ─────────────────────────────────────────────────────────────
# CATALOG CACHING  (cuts repeated dedup queries; default LocMemCache)
# ─────────────────────────────────────────────────────────────
HOME_CACHE_KEY = "catalog:home_v1"
HOME_CACHE_TTL = 120          # seconds
FILTER_CACHE_TTL = 60         # seconds

HOMEPAGE_MARKETPLACES = [
    ("flipkart", "Flipkart", "Big Billion drops & everyday low prices"),
    # ("myntra",   "Myntra",   "Fashion & lifestyle offers"),
    # ("ajio",     "Ajio",     "Trendy styles, hand-picked deals"),
]


def get_homepage_data():
    """
    Cached homepage payload: the Amazon grid + each marketplace section.
    Evaluates the (expensive) dedup queries once per HOME_CACHE_TTL instead
    of on every request. Products keep their select_related('link') so the
    template never fires per-card queries.
    """
    data = cache.get(HOME_CACHE_KEY)
    if data is None:
        data = {
            "amazon": list(build_product_queryset(source="amazon")[:HOMEPAGE_MAX]),
            "marketplaces": [
                {"key": k, "label": label, "tagline": tagline,
                 "products": list(build_product_queryset(source=k)[:TRENDING_LIMIT])}
                for (k, label, tagline) in HOMEPAGE_MARKETPLACES
            ],
        }
        cache.set(HOME_CACHE_KEY, data, HOME_CACHE_TTL)
    return data


def get_filtered_products(category, source):
    """
    Cached, fully-deduped product list for a category/source filter, so the
    two dedup sub-queries run once per FILTER_CACHE_TTL rather than per page.
    Returns a list (paginate it with Paginator).
    """
    key = "catalog:filter:" + (category or "-").lower() + ":" + (source or "-").lower()
    items = cache.get(key)
    if items is None:
        items = list(build_product_queryset(category=category or None, source=source or None))
        cache.set(key, items, FILTER_CACHE_TTL)
    return items


def bust_catalog_cache():
    """Drop the homepage cache so newly added/converted products show at once."""
    cache.delete(HOME_CACHE_KEY)


def compact_page_range(page_obj, width=2):
    """
    Page numbers to show in numbered pagination: first, last, and a window
    around the current page. None marks an ellipsis gap.
    e.g. current=6 of 20 -> [1, None, 4,5,6,7,8, None, 20]
    """
    cur = page_obj.number
    last = page_obj.paginator.num_pages
    out = []
    for n in range(1, last + 1):
        if n == 1 or n == last or (cur - width <= n <= cur + width):
            out.append(n)
        elif out and out[-1] is not None:
            out.append(None)
    return out


def add_product_page(request):
    return render(request, 'products/add_product.html')


def favicon(request):
    """Browser tab icon for every page — redirects /favicon.ico to the logo."""
    from django.templatetags.static import static
    return redirect(static('products/images/logo.png'))


def _parse_amount(text):
    """Best-effort numeric extraction from a price string like '₹1,299.00'."""
    if not text:
        return None
    cleaned = re.sub(r"[^\d.]", "", str(text).replace(",", ""))
    try:
        return round(float(cleaned), 2) if cleaned else None
    except ValueError:
        return None


@staff_member_required
def manual_add_product(request):
    """
    Staff-only manual upload page (gated behind the Django admin login).
    GET  /upload/  -> styled form
    POST /upload/  -> creates a Product + AmazonLink for any source
                      (amazon / flipkart / myntra / ajio).
    """
    ctx = {
        "categories": STRIP_CATEGORIES,
        "sources": Product.SOURCE_CHOICES,
    }

    if request.method == "POST":
        source = (request.POST.get("source") or "amazon").strip().lower()
        title = (request.POST.get("title") or "").strip()
        product_url = (request.POST.get("product_url") or "").strip()
        image_url = (request.POST.get("image_url") or "").strip()
        category = (request.POST.get("category") or "").strip()
        description = (request.POST.get("description") or "").strip()
        price_display = (request.POST.get("price_display") or "").strip()
        mrp_display = (request.POST.get("mrp_display") or "").strip()
        discount_raw = (request.POST.get("discount_percentage") or "").strip()
        asin = (request.POST.get("asin") or "").strip() or None

        if not title or not product_url:
            ctx["error"] = "Title and Product URL are required."
            return render(request, "products/manual_add.html", ctx)

        valid_sources = {s for s, _ in Product.SOURCE_CHOICES}
        if source not in valid_sources:
            source = "amazon"

        discount = None
        if discount_raw:
            digits = re.sub(r"[^\d]", "", discount_raw)
            discount = int(digits) if digits else None

        # Auto-compute discount when MRP and price are both numeric and none given.
        price_amount = _parse_amount(price_display)
        mrp_amount = _parse_amount(mrp_display)
        if discount is None and price_amount and mrp_amount and mrp_amount > 0:
            discount = round((1 - (price_amount / mrp_amount)) * 100)

        link = AmazonLink.objects.create(
            product_url=product_url,
            title=title,
            asin=asin,
        )
        product = Product.objects.create(
            link=link,
            source=source,
            category=category,
            title=title,
            description=description,
            image_url=image_url,
            price_display=price_display,
            price_amount=price_amount,
            mrp_display=mrp_display,
            mrp_amount=mrp_amount,
            discount_percentage=discount,
        )

        ctx["success"] = f"Added “{title}” ({source.title()}). Slug: {link.slug}"
        bust_catalog_cache()   # show the new product on the homepage immediately
        return render(request, "products/manual_add.html", ctx)

    return render(request, "products/manual_add.html", ctx)


def product_list(request):
    category = (request.GET.get("category") or "").strip()
    source = (request.GET.get("source") or "").strip().lower()
    page_number = request.GET.get("page", 1)

    # "All Deals" / empty / "all" means the unfiltered homepage.
    cat_is_all = category.lower() in ("", "all", "all deals")
    is_filtered = (not cat_is_all) or bool(source)

    # ── FILTERED / "SEE ALL" VIEW (numbered pagination + product count) ──
    if is_filtered:
        items = get_filtered_products(
            category=None if cat_is_all else category,
            source=source or None,
        )
        paginator = Paginator(items, CATEGORY_PAGE_SIZE)
        page_obj = paginator.get_page(page_number)

        # Active filter preserved in pagination links.
        filter_pairs = []
        if not cat_is_all:
            filter_pairs.append(("category", category))
        if source:
            filter_pairs.append(("source", source))
        filter_qs = urlencode(filter_pairs)

        banner_image = None
        if source in ("flipkart", "myntra", "ajio"):
            banner_image = f"products/images/banner-{source}.png"

        return render(request, "products/product_list.html", {
            "page_obj": page_obj,
            "page_range": compact_page_range(page_obj),
            "categories": STRIP_CATEGORIES,
            "active_category": category if not cat_is_all else (source.title() if source else "All Deals"),
            "is_filtered": True,
            "filter_qs": filter_qs,
            "banner_image": banner_image,
            "trending_products": [],
        })

    # ── HOMEPAGE (capped Amazon grid + "See all" buttons; no infinite scroll) ──
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return HttpResponse("")   # homepage doesn't infinite-scroll

    home = get_homepage_data()    # cached; busted on new products
    return render(request, "products/product_list.html", {
        "page_obj": home["amazon"][:HOMEPAGE_SHOW],
        "show_all_amazon": len(home["amazon"]) > HOMEPAGE_SHOW,
        "categories": STRIP_CATEGORIES,
        "active_category": "All Deals",
        "is_filtered": False,
        "filter_qs": "",
        "marketplaces": home["marketplaces"],
    })


def product_detail(request, slug):
    product = get_object_or_404(
        Product.objects.select_related('link'),
        link__slug=slug,
    )

    # Count one view per browser session per product (refreshes don't inflate).
    seen = request.session.get('viewed', [])
    if slug not in seen:
        Product.objects.filter(pk=product.pk).update(views=F('views') + 1)
        product.views = (product.views or 0) + 1
        seen.append(slug)
        request.session['viewed'] = seen[-300:]

    context = {
        'product': product,
        'detail': build_product_detail_context(product),
    }
    return render(request, 'products/product_detail.html', context)


# views.py
def build_product_detail_context(product):
    """
    Shapes all extended product parameters into a single standard context structure
    consumed simultaneously by HTML templates and JSON API endpoints.
    """
    has_price = product.price_amount is not None
    has_mrp = product.mrp_amount is not None

    discount_percentage = product.discount_percentage
    if discount_percentage is None and has_price and has_mrp and product.mrp_amount > 0:
        discount_percentage = round((1 - (product.price_amount / product.mrp_amount)) * 100)

    dimensions_parts = [d for d in [product.dimension_height, product.dimension_length, product.dimension_width] if d]
    dimensions_display = " × ".join(dimensions_parts) if dimensions_parts else ""

    return {
        'pricing': {
            'price_amount': product.price_amount,
            'price_display': product.price_display,
            'price_currency': product.price_currency,
            'mrp_amount': product.mrp_amount,
            'mrp_display': product.mrp_display,
            'mrp_label': product.mrp_label or 'MRP',
            'discount_percentage': discount_percentage,
            'savings_amount': product.savings_amount,
            'savings_display': product.savings_display,
            'has_price': has_price,
            'has_mrp': has_mrp,
            'has_discount': bool(discount_percentage),
        },
        'availability': {
            'message': product.availability_message,
            'type': product.availability_type,
            'condition': product.condition,
            'merchant_name': product.merchant_name,
            'is_buy_box_winner': product.is_buy_box_winner,
            'listing_type': product.listing_type,
        },
        'deal': {
            'type': product.deal_type,
            'end_time': product.deal_end_time,
            'is_active': bool(product.deal_type),
        },
        'specs': {
            'brand': product.brand,                     # Brand Name
            'category': product.product_group,          # Product Category
            'manufacturer': product.manufacturer,
            'product_group': product.product_group,
            'binding': product.binding,
            'item_part_number': product.item_part_number,
            'model_number': product.model_number,
            'warranty': product.warranty,
            'color': product.color,
            'size': product.size,
            'unit_count': product.unit_count,
            'dimensions_display': dimensions_display,
            'weight': product.dimension_weight,
        },
        'features': product.features or [],              # Product features array
        'variant_images': product.variant_images or [],  # Variant images list
        'category_rankings': product.category_rankings or [],
        'last_checked_at': product.last_checked_at,
    }


@api_view(["GET"])
def product_detail_api(request, slug):
    """
    GET /api/products/<slug>/detail/
    Returns full product details as JSON.
    """
    product = get_object_or_404(Product.objects.select_related('link'), link__slug=slug)
    data = {
        'title': product.title or product.link.title,
        'slug': product.link.slug,
        'description': product.description,
        'image_url': product.image_url,
        'product_url': product.link.product_url,
        **build_product_detail_context(product),
    }
    return Response(data)
# ==========================================
# 1b. API — PRODUCT DETAIL (price/MRP/specs/availability)
# ==========================================




# ==========================================
# 2. REDIRECT ENGINE
# ==========================================

RESERVED_PATHS = {
    'api', 'admin', 'product', 'add-product', 'upload', 'show-data', 'convert', 'accounts',
    'privacy-policy', 'terms', 'contact',
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
# NOTE: ProductListCreateAPIView is defined once, lower in this file
# (the version that also supports DELETE).


def extract_asin(url):
    """
    Pull a 10-char Amazon ASIN out of a product OR search/browse URL.
    Handles /dp/, /gp/product/, asin=, hidden-keywords=, and the ASIN hidden
    inside a search filter like  rh=p_78%3AB0FMS47419  ( %3A == ':' ).
    """
    from urllib.parse import unquote
    u = unquote(url)  # decode %3A etc. so rh=p_78:ASIN is readable

    patterns = [
        r'/(?:dp|gp/product|gp/aw/d|product)/([A-Z0-9]{10})',
        r'/dp/([A-Z0-9]{10})',
        r'[?&](?:asin|ASIN)=([A-Z0-9]{10})',
        r'[?&]hidden-keywords=([A-Z0-9]{10})',
        r'p_78[:=]([A-Z0-9]{10})',          # search filter: rh=p_78:ASIN
        r'\bnode[:=]([A-Z0-9]{10})\b',       # some browse filters
    ]
    for pat in patterns:
        m = re.search(pat, u)
        if m:
            return m.group(1)
    return None


def extract_all_asins(url):
    """
    Return every distinct ASIN in a URL, in order — for search links that filter
    on multiple products, e.g. rh=p_78%3AB0FMS47419%7Cp_78%3AB0XXXXXXXX.
    Falls back to the single extract_asin result.
    """
    from urllib.parse import unquote
    u = unquote(url)
    found = []
    for pat in (r'/(?:dp|gp/product|gp/aw/d|product)/([A-Z0-9]{10})',
                r'p_78[:=]([A-Z0-9]{10})',
                r'[?&](?:asin|ASIN)=([A-Z0-9]{10})',
                r'[?&]hidden-keywords=([A-Z0-9]{10})'):
        for m in re.finditer(pat, u):
            if m.group(1) not in found:
                found.append(m.group(1))
    if not found:
        one = extract_asin(url)
        if one:
            found.append(one)
    return found


def convert_and_upsert(raw_url, tag):
    """
    Shared pipeline used by both /api/shorten/ and /api/convert/:
      clean + apply affiliate tag -> extract ASIN -> fetch via Creators API
      -> create/refresh the Product (one row per ASIN).

    Returns (product, amazon_link, long_url, error) where `error` is None on
    success, or a human-readable string when something failed.
    """
    # Keyword/search links stay as search links (full listing) -> tag + shorten.
    if is_search_link(raw_url):
        short = shorten_url(clean_search_url(raw_url, tag))[0]
        return None, None, short, None

    tagged = clean_and_tag_url(raw_url, tag)

    asin = extract_asin(tagged)
    if not asin:
        return None, None, tagged, "Could not extract a valid Amazon ASIN from the provided URL."

    # Store a clean, canonical affiliate URL (keeps product_url short and tidy,
    # and avoids overflowing the DB column with Amazon's tracking params).
    netloc = urlparse(tagged).netloc or "www.amazon.in"
    long_url = f"https://{netloc}/dp/{asin}?tag={tag}"

    product_data = fetch_product_from_creators_api(asin, tag)
    if not product_data:
        # No catalog data from Amazon for this ASIN. Do NOT fail -- return a
        # clean, tagged, SHORTENED link so the deal can still be shared.
        short = shorten_url(long_url)[0]
        return None, None, short, None

    fetched_title = product_data.get("title", "Amazon Product")
    derived_category = derive_amazon_category(product_data)

    # Reuse the record for this ASIN *and tag* (so re-converting with the same
    # tag refreshes one page), but a different tag creates its own page so each
    # bot keeps its own affiliate tag. The homepage still shows one card per
    # ASIN via build_product_queryset's de-duplication.
    amazon_link = AmazonLink.objects.filter(asin=asin, tag=tag).order_by("-id").first()
    if amazon_link:
        amazon_link.product_url = long_url            # refresh the affiliate link
        amazon_link.title = fetched_title
        amazon_link.save()
    else:
        amazon_link = AmazonLink.objects.create(
            product_url=long_url,
            title=fetched_title,
            asin=asin,
            tag=tag,
        )

    product, _ = Product.objects.update_or_create(
        link=amazon_link,
        defaults=dict(
            source="amazon",
            category=derived_category,
            title=fetched_title,
            image_url=product_data.get("primary_image", ""),
            variant_images=product_data.get("all_images", []),
            features=product_data.get("features", []),
            price_display=product_data.get("price", "Check on Amazon"),
            price_amount=product_data.get("price_amount"),
            price_currency=product_data.get("price_currency", "INR"),
            mrp_display=product_data.get("mrp_display", ""),
            mrp_amount=product_data.get("mrp_amount"),
            discount_percentage=product_data.get("discount_percentage"),
            savings_display=product_data.get("savings_display", ""),
            savings_amount=product_data.get("savings_amount"),
            overall_rank=product_data.get("overall_rank"),
            overall_rank_context=product_data.get("overall_rank_context", ""),
            category_rankings=product_data.get("category_rankings", []),
        ),
    )
    bust_catalog_cache()   # new/updated product -> refresh homepage
    return product, amazon_link, long_url, None


# @csrf_exempt
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

    product, amazon_link, long_url, error = convert_and_upsert(raw_url, tag)
    if error:
        code = 400 if "ASIN" in error else 500
        return Response({"error": error}, status=code)

    if amazon_link is None:
        # PA-API had no data -> a shortened tagged link was returned instead.
        return Response({"status": "success", "type": "short_link", "short_url": long_url})

    # Build the custom internal redirection link reference
    domain = getattr(settings, "SHORTENER_DOMAIN", "https://dealhunts.in").rstrip('/')
    product_page_url = f"{domain}/product/{amazon_link.slug}/"

    return Response({
        "status": "success",
        "product_id": product.id,
        "slug": amazon_link.slug,
        "product_page_url": product_page_url,
        "amazon_affiliate_url": amazon_link.product_url,
        "data": {
            "title": product.title,
            "image": product.image_url,
            "pricing": {
                "price": product.price_display,
                "price_raw": product.price_amount,
                "mrp": product.mrp_display,
                "mrp_raw": product.mrp_amount,
                "discount_percent": f"{product.discount_percentage}% off" if product.discount_percentage else None,
                "savings": product.savings_display
            },
            "rankings": {
                "overall_site_rank": product.overall_rank,
                "overall_site_context": product.overall_rank_context,
                "categories": product.category_rankings
            }
        }
    }, status=status.HTTP_201_CREATED)


# Affiliate-bot display name -> Amazon Associates tracking tag.
# Populates the converter page's "Affiliate bot" dropdown so the tag is
# selected automatically when a bot name is chosen.
AFFILIATE_BOTS = {
    "ASH":             "ashfiyarajguru-21",
    "DH AFFILIATE BOT":          "banalibanerjee-21",
    "POOJA AFFILIATE BOT":       "alena01-21",
    "Rohin Affiliate Bot":       "lootlobhai-21",
    "Jaincy Affiliate Bot":      "0c0-21",
    "Karishma Affiliate Bot":    "brandinteger01-21",
    "Priyansh Affiliate Bot":    "chandanmallah-21",
    "Siddhant Affiliate Bot":    "pragyajain00-21",
    "Dabang affiliate bot":      "fbh049-21",
    "KULDEEP AFFILIATE BOT":     "kuldeepsingh01-21",
    "Renuka Affiliate Bot":      "priyanshgupta02-21",
    "Naman Affiliate Bot":       "saurabhrathore-21",
    "Kanika affiliate bot":      "chandanmallah-21",
    "ADMIN":    "indiantester01-21",
    "Arif Affiliate Bot":        "dabangg00-21",
    "Harsh Affiliate Bot":       "cmar01-21",
    "Prashant Affiliate Bot":    "282807-21",
    "Karmveer Affiliate Bot":    "earnkaro0a7-21",
    "Pooja Main Affiliate Bot":  "harharmahadev0c-21",
    "Keyword Link":              "keyword04-21",
    "Devil Affiliate Bot":       "saurabhrathore00-21",
    # "Swati Singh AFFILIATE BOT": "sehajdeepkaur-21",
}


@api_view(["POST"])
def convert_affiliate_link(request):
    """
    Affiliate link converter.
    POST /api/convert/
    Body: { "url": "<amazon product url>", "tag": "<affiliate tag>" }

    Tags + fetches the product, posts it to the site, and returns the
    shareable product page URL built from THIS host (e.g.
    http://127.0.0.1:8000/product/upp-6g1/ in dev, your domain in prod).
    """
    raw_url = (request.data.get("url") or request.data.get("product_url") or "").strip()
    tag     = (request.data.get("tag") or "kuldeepsingh01-21").strip()

    if not raw_url:
        return Response({"error": "url is required"}, status=400)
    if not tag:
        return Response({"error": "tag is required"}, status=400)

    product, amazon_link, long_url, error = convert_and_upsert(raw_url, tag)
    if error:
        code = 400 if "ASIN" in error else 502
        return Response({"error": error}, status=code)

    if amazon_link is None:
        return Response({"status": "success", "type": "short_link", "short_url": long_url})

    # Shareable link based on the actual request host (works in dev + prod).
    product_page_url = request.build_absolute_uri(f"/product/{amazon_link.slug}/")

    return Response({
        "status": "success",
        "slug": amazon_link.slug,
        "product_page_url": product_page_url,     # <- share this with buyers
        "affiliate_url": amazon_link.product_url,  # tagged Amazon link
        "preview": {
            "title": product.title,
            "image": product.image_url,
            "price": product.price_display,
            "mrp": product.mrp_display,
            "discount_percent": product.discount_percentage,
            "category": product.category,
        },
    }, status=status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────
# BULK MESSAGE LINK REWRITING
# ─────────────────────────────────────────────────────────────

SHORT_AMAZON_HOSTS = {"amzn.to", "amzn.in", "a.co", "amzn.eu", "amzn.asia", "link.amazon", "l.amazon"}


def is_amazon_host(netloc):
    h = (netloc or "").lower()
    if h.startswith("www."):
        h = h[4:]
    return (
        h in SHORT_AMAZON_HOSTS
        or "amazon." in h          # amazon.in, amazon.com, ...
        or h.endswith(".amazon")   # link.amazon, l.amazon, ...
        or h == "amazon"
    )


def resolve_amazon_url(url):
    """Follow a short/redirecting Amazon link to its final product URL."""
    headers = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/122.0 Safari/537.36")
    }
    try:
        r = requests.head(url, allow_redirects=True, timeout=10, headers=headers)
        if extract_asin(r.url):
            return r.url
    except Exception:
        pass
    try:
        r = requests.get(url, allow_redirects=True, timeout=12, headers=headers)
        return r.url
    except Exception:
        return None


def upsert_search_link(search_url, tag):
    """
    Fallback for Amazon links that have NO ASIN (keyword search links).
    We can't fetch product data, so we just re-tag the URL and post a minimal
    product whose 'Buy on Amazon' points at the tagged search URL.
    Reuses an existing row for the same tagged URL so it doesn't duplicate.
    """
    long_url = clean_and_tag_url(search_url, tag)

    # Derive a readable title from the search keywords (?k=...).
    kw = parse_qs(urlparse(long_url).query).get("k", [""])[0]
    title = (kw.replace("+", " ").strip() or "Amazon search").title()

    link = AmazonLink.objects.filter(product_url=long_url).order_by("-id").first()
    if link:
        link.title = title
        link.tag = tag
        link.save()
    else:
        link = AmazonLink.objects.create(product_url=long_url, title=title, asin=None, tag=tag)

    product, _ = Product.objects.update_or_create(
        link=link,
        defaults=dict(
            source="amazon",
            title=title,
            category="",
            price_display="View options on Amazon",
        ),
    )
    bust_catalog_cache()
    return product, link, long_url


def rewrite_message_links(message, tag, link_type, request):
    """
    Find every Amazon link in `message` and replace it, leaving all other text
    (codes, form links, formatting) untouched.

    link_type:
      "amazon" -> replace with a re-tagged full Amazon URL (fast; no fetch/post)
      "page"   -> fetch + post the product, replace with its product page URL
    Returns (converted_message, items, errors).
    """
    url_re = re.compile(r'https?://[^\s*<>"\']+')
    mapping = {}
    items, errors = [], []
    processed = set()

    for raw in url_re.findall(message):
        token = raw.rstrip('.,);:|*')
        if token in processed:
            continue
        processed.add(token)

        parsed = urlparse(token)
        if not is_amazon_host(parsed.netloc):
            continue  # leave non-Amazon links (forms, etc.) untouched

        # Each link is isolated: any failure is recorded and we move on.
        try:
            # STEP 1 — expand the link to its final URL first (amzn.to /
            # link.amazon / a.co / regional shorteners and any redirect).
            full = token
            if not extract_asin(full):
                full = resolve_amazon_url(token)
            if not full:
                errors.append({"url": token, "reason": "Could not resolve link."})
                continue

            # Keyword/search links stay as search links (full listing).
            if is_search_link(full):
                short = shorten_url(clean_search_url(full, tag))[0]
                mapping[token] = short
                items.append({"original": token, "asin": None,
                              "replacement": short, "title": "Amazon search"})
                continue

            # STEP 2 — collect every ASIN. A product link has one; a filtered
            # search link may have several; a keyword search link has none.
            asins = extract_all_asins(full)
            netloc = urlparse(full).netloc or "www.amazon.in"
            reps = []

            if asins:
                for asin in asins:
                    canonical = f"https://{netloc}/dp/{asin}?tag={tag}"
                    product, amazon_link, long_url, error = convert_and_upsert(canonical, tag)
                    if error:
                        errors.append({"url": token, "asin": asin, "reason": error})
                        continue
                    if amazon_link is None:
                        # No PA-API data -> use the shortened tagged link.
                        reps.append(long_url)
                        items.append({"original": token, "asin": asin,
                                      "replacement": long_url, "title": "Amazon deal"})
                        continue
                    if link_type == "page":
                        reps.append(request.build_absolute_uri(f"/product/{amazon_link.slug}/"))
                    else:
                        reps.append(amazon_link.product_url)
                    items.append({"original": token, "asin": asin,
                                  "replacement": reps[-1], "title": product.title})
            else:
                product, amazon_link, long_url = upsert_search_link(full, tag)
                reps.append(request.build_absolute_uri(f"/product/{amazon_link.slug}/")
                            if link_type == "page" else long_url)
                items.append({"original": token, "asin": None,
                              "replacement": reps[-1], "title": product.title})

            if reps:
                mapping[token] = "\n".join(reps)
        except Exception as e:
            errors.append({"url": token, "reason": f"Unexpected error: {e}"})
            continue

    # ── Bare ASINs typed directly (not inside a URL), e.g. "B0FMS47419" ──
    # Must be a standalone 10-char token containing at least one digit AND one
    # letter (so plain words / phone numbers aren't mistaken for ASINs).
    asin_token_re = re.compile(r'(?<![\w/-])([A-Z0-9]{10})(?![\w/-])')
    for m in asin_token_re.finditer(message):
        tok = m.group(1)
        if tok in processed:
            continue
        if not (re.search(r'[0-9]', tok) and re.search(r'[A-Z]', tok)):
            continue
        processed.add(tok)
        try:
            canonical = f"https://www.amazon.in/dp/{tok}?tag={tag}"
            product, amazon_link, long_url, error = convert_and_upsert(canonical, tag)
            if error:
                errors.append({"url": tok, "reason": error})
                continue
            if amazon_link is None:
                mapping[tok] = long_url   # shortened tagged link (no PA-API data)
                items.append({"original": tok, "asin": tok,
                              "replacement": long_url, "title": "Amazon deal"})
                continue
            rep = (request.build_absolute_uri(f"/product/{amazon_link.slug}/")
                   if link_type == "page" else amazon_link.product_url)
            mapping[tok] = rep
            items.append({"original": tok, "asin": tok,
                          "replacement": rep, "title": product.title})
        except Exception as e:
            errors.append({"url": tok, "reason": f"Unexpected error: {e}"})
            continue

    # ── Apply replacements ──
    converted = message
    # URLs first, longest-first (so one URL isn't a prefix of another).
    url_keys = sorted((k for k in mapping if k.startswith("http")), key=len, reverse=True)
    for token in url_keys:
        converted = converted.replace(token, mapping[token])
    # Bare ASINs with word boundaries, so we don't touch an ASIN that now sits
    # inside an already-inserted /dp/ASIN URL.
    for token in (k for k in mapping if not k.startswith("http")):
        rep = mapping[token]
        converted = re.sub(r'(?<![\w/-])' + re.escape(token) + r'(?![\w/-])',
                           lambda _m, r=rep: r, converted)

    return converted, items, errors


@api_view(["POST"])
def convert_message(request):
    """
    Bulk message converter.
    POST /api/convert-message/
    Body: { "message": "<full text>", "tag": "<tag>", "link_type": "amazon"|"page" }

    Returns the same message with every Amazon link re-tagged (or swapped for a
    product page link), preserving all other content and formatting.
    """
    message = (request.data.get("message") or "").strip()
    bot = (request.data.get("bot") or "").strip()
    # Resolve the bot name to its tag server-side (tag is never sent to the client).
    tag = AFFILIATE_BOTS.get(bot) or (request.data.get("tag") or "kuldeepsingh01-21").strip()
    link_type = (request.data.get("link_type") or "amazon").strip().lower()
    if link_type not in ("amazon", "page"):
        link_type = "amazon"

    if not message:
        return Response({"error": "message is required"}, status=400)

    converted, items, errors = rewrite_message_links(message, tag, link_type, request)
    return Response({
        "status": "success",
        "converted_message": converted,
        "converted_count": len(items),
        "items": items,
        "errors": errors,
    })


@ensure_csrf_cookie
def affiliate_converter(request):
    """
    Unlisted converter UI (no nav link anywhere). Visit /convert/ directly.
    The page posts to /api/convert/ and shows the shareable product page link.
    """
    return render(request, "products/affiliate_converter.html", {
        "bots": list(AFFILIATE_BOTS.keys()),
        "default_bot": "KULDEEP AFFILIATE BOT",
    })

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


#Extra

# Add this template-serving view definition anywhere inside views.py
def show_data_page(request):
    """Renders the standard system database admin control matrix workspace."""
    products_list = Product.objects.select_related('link').all().order_by('-created_at')
    paginator = Paginator(products_list, 15) # Show 15 assets per page matrix run
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    return render(request, 'products/show_data.html', {'page_obj': page_obj})


# Then, UPDATE your existing ProductListCreateAPIView to support deletions:
class ProductListCreateAPIView(APIView):
    def get(self, request):
        """
        GET /api/products/?category=<label>&source=<platform>&page=<n>&page_size=<n>
        Returns a paginated, ASIN-deduplicated envelope:
            { "count", "page", "num_pages", "has_next", "results": [...] }
        """
        category = (request.GET.get("category") or "").strip()
        source = (request.GET.get("source") or "").strip().lower()
        if category.lower() in ("all", "all deals"):
            category = ""

        qs = build_product_queryset(category=category or None, source=source or None)

        try:
            page_size = max(1, min(int(request.GET.get("page_size", CATEGORY_PAGE_SIZE)), 100))
        except (TypeError, ValueError):
            page_size = CATEGORY_PAGE_SIZE

        paginator = Paginator(qs, page_size)
        page_obj = paginator.get_page(request.GET.get("page", 1))
        serializer = ProductSerializer(page_obj.object_list, many=True)

        return Response({
            "count": paginator.count,
            "page": page_obj.number,
            "num_pages": paginator.num_pages,
            "has_next": page_obj.has_next(),
            "results": serializer.data,
        })

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            product = serializer.save()
            return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request):
        """Processes cascade deletions matching selected link index tokens securely."""
        target_id = request.data.get("id")
        if not target_id:
            return Response({"error": "Missing parameter constraint identifying column: id"}, status=400)
            
        # Select link row. CASCADE setup on Product deletes child metrics automatically.
        link_entry = get_object_or_404(AmazonLink, id=target_id)
        link_entry.delete()
        
        return Response({"success": True, "message": "Product asset metadata scrubbed successfully."})
    


#delete api

class EnforceCatalogRetentionAPIView(APIView):
    """
    POST /api/products/cleanup/
    Enforces a strict 300-entry retention limit. Deletes all older records.
    """
    def post(self, request):
        try:
            with transaction.atomic():
                # Find the primary key ID of the 300th newest record
                cutoff_link = AmazonLink.objects.order_by('-id').values_list('id', flat=True)[200:201]
                
                if cutoff_link:
                    cutoff_id = cutoff_link[0]
                    
                    # Target all links added before (or with an ID lower than) our cutoff
                    to_delete = AmazonLink.objects.filter(id__lte=cutoff_id)
                    deleted_count, _ = to_delete.delete()
                    
                    return Response({
                        "success": True,
                        "message": f"Data retention check complete. Purged {deleted_count} older entries.",
                        "remaining_limit": 200
                    })
                
                return Response({
                    "success": True,
                    "message": "Database size is within safe margins. Active items are under the 300 entry threshold.",
                    "current_count": AmazonLink.objects.count()
                })
                
        except Exception as e:
            return Response({
                "success": False,
                "error": f"Internal infrastructure error during retention execution: {str(e)}"
            }, status=500)
        

def privacy_policy(request):
    return render(request, 'products/privacy_policy.html')


def terms(request):
    return render(request, 'products/terms.html')


def contact(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            # Tries to email support; fail_silently so a missing mail config
            # never 500s — the user still sees the confirmation below.
            try:
                send_mail(
                    subject=f"[Contact] {cd['subject']}",
                    message=f"From: {cd['name']} <{cd['email']}>\n\n{cd['message']}",
                    from_email=None,  # uses DEFAULT_FROM_EMAIL
                    recipient_list=["support@dealsforfree.in"],
                    fail_silently=True,
                )
            except Exception:
                pass
            messages.success(request, "Thanks — your message has been sent. We'll get back to you soon.")
            return redirect("contact")
        messages.error(request, "Please correct the highlighted fields and try again.")
    else:
        form = ContactForm()
    return render(request, "products/contact.html", {"form": form})


@csrf_exempt
@api_view(["POST"])
def bot_convert(request):
    """
    POST /api/bot-convert/
    Body: {"url": "<amazon url>", "tag": "<affiliate tag>"}
    Runs convert_and_upsert (full PA-API fetch, saves the product, dedups by
    ASIN) and returns the product-page link — or a short link when there's no
    product data / it's a search link.
    """
    url = (request.data.get("url") or "").strip()
    tag = (request.data.get("tag") or "kuldeepsingh01-21").strip()
    if not url:
        return Response({"status": "error", "error": "url is required"}, status=400)

    product, link, long_url, error = convert_and_upsert(url, tag)
    if error:
        return Response({"status": "error", "error": error}, status=200)

    # No product (PA-API had no data, or it was a search link) -> short link.
    if link is None:
        return Response({"status": "success", "type": "short_link", "short_url": long_url})

    return Response({
        "status": "success",
        "type": "product",
        "slug": link.slug,
        "product_url": request.build_absolute_uri(f"/product/{link.slug}/"),
        "title": product.title,
        "price": product.price_display,
        "mrp": product.mrp_display,
        "discount": product.discount_percentage,
    })    



def _tv_send_telegram(text):
    """Send a signal to the trading Telegram chat (TV_* settings, else TELEGRAM_*)."""
    import json as _json, urllib.request
    from django.conf import settings as _s
    token = getattr(_s, "TV_TELEGRAM_BOT_TOKEN", "") or getattr(_s, "TELEGRAM_BOT_TOKEN", "")
    chat = getattr(_s, "TV_TELEGRAM_CHAT_ID", "") or getattr(_s, "TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        print("[tv] telegram not configured")
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = _json.dumps({"chat_id": chat, "text": text, "parse_mode": "HTML",
                        "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        urllib.request.urlopen(req, timeout=15)
        return True
    except Exception as e:
        print(f"[tv] telegram error: {e}")
        return False


def _format_tv_signal(d):
    """Turn a TradingView JSON alert into a tidy Telegram message."""
    action = str(d.get("action") or d.get("side") or "").lower()
    emoji = {"buy": "🟢", "long": "🟢", "sell": "🔴", "short": "🔴",
             "exit": "⚪", "close": "⚪"}.get(action, "📈")
    labels = {"ticker": "Ticker", "symbol": "Ticker", "exchange": "Exchange",
              "action": "Action", "side": "Side", "price": "Price", "close": "Price",
              "sl": "Stop Loss", "stoploss": "Stop Loss", "tp": "Target",
              "target": "Target", "qty": "Qty", "quantity": "Qty",
              "strategy": "Strategy", "interval": "Timeframe", "tf": "Timeframe",
              "time": "Time", "timenow": "Time", "note": "Note",
              "message": "Message", "comment": "Comment"}
    order = ["ticker", "symbol", "exchange", "action", "side", "price", "close",
             "sl", "stoploss", "tp", "target", "qty", "quantity", "strategy",
             "interval", "tf", "time", "timenow", "note", "message", "comment"]
    lines = [f"{emoji} <b>TradingView Signal</b>", ""]
    seen = set()
    for k in order:
        if k in d and k != "secret" and d[k] not in (None, ""):
            lbl = labels.get(k, k.title())
            if lbl in seen:
                continue
            seen.add(lbl)
            lines.append(f"<b>{lbl}:</b> {d[k]}")
    for k, v in d.items():
        if k == "secret" or k in order or v in (None, ""):
            continue
        lines.append(f"<b>{str(k).title()}:</b> {v}")
    return "\n".join(lines)


# @csrf_exempt
# def tradingview_webhook(request, secret=None):
#     """Receive a TradingView alert and forward it to Telegram.
#     Auth: secret in the URL path, or a "secret" field in the JSON body."""
#     import json as _json
#     from django.conf import settings as _s
#     if request.method == "GET":
#         return HttpResponse("TradingView webhook is live.", content_type="text/plain")
#     if request.method != "POST":
#         return HttpResponse(status=405)

#     expected = getattr(_s, "TV_WEBHOOK_SECRET", "")
#     raw = request.body.decode("utf-8", "ignore").strip()
#     try:
#         payload = _json.loads(raw)
#     except Exception:
#         payload = None

#     provided = secret or (payload.get("secret") if isinstance(payload, dict) else None)
#     if not expected or provided != expected:
#         return HttpResponse("unauthorized", status=401)

#     if isinstance(payload, dict):
#         text = _format_tv_signal(payload)
#     else:
#         text = "📈 <b>TradingView Signal</b>\n\n" + (raw or "(empty alert)")
#     _tv_send_telegram(text)
#     return HttpResponse("ok", content_type="text/plain")    

@csrf_exempt
def tradingview_webhook(request, secret=None):
    """Receive a TradingView alert and forward it to Telegram.
    Auth: secret in the URL path, or a "secret" field in the JSON body."""
    import json as _json
    from django.conf import settings as _s
    if request.method == "GET":
        return HttpResponse("TradingView webhook is live.", content_type="text/plain")
    if request.method != "POST":
        return HttpResponse(status=405)

    expected = getattr(_s, "TV_WEBHOOK_SECRET", "")
    raw = request.body.decode("utf-8", "ignore").strip()
    print(f"[tv] incoming POST, raw body: {raw[:500]}")

    try:
        payload = _json.loads(raw)
    except Exception as e:
        print(f"[tv] JSON parse failed: {e} | raw={raw[:300]}")
        payload = None

    provided = secret or (payload.get("secret") if isinstance(payload, dict) else None)
    if not expected or provided != expected:
        print(f"[tv] unauthorized: provided={provided!r} expected_set={bool(expected)}")
        return HttpResponse("unauthorized", status=401)

    if isinstance(payload, dict):
        text = _format_tv_signal(payload)
    else:
        text = "📈 <b>TradingView Signal</b>\n\n" + (raw or "(empty alert)")

    sent = _tv_send_telegram(text)
    print(f"[tv] telegram sent={sent}")
    return HttpResponse("ok", content_type="text/plain")