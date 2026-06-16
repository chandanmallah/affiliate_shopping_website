from django.shortcuts import render, get_object_or_404, redirect
from django.core.cache import cache
from django.conf import settings

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.decorators import api_view

from .models import Product, ShortURL, AmazonLink
from .serializers import ProductSerializer

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ShortURL

# ==========================================
# 1. HTML PAGE VIEWS
# ==========================================

def add_product_page(request):
    return render(request, 'products/add_product.html')


def product_list(request):
    # select_related('link') keeps this fast by joining tables in 1 query
    products = Product.objects.select_related('link').all().order_by('-created_at')
    return render(request, 'products/product_list.html', {'products': products})   


def product_detail(request, slug):
    product = get_object_or_404(Product, link__slug=slug)
    return render(request, 'products/product_detail.html', {'product': product})


# ==========================================
# 2. ULTRA-FAST REDIRECTION (MILLISECOND SPEED)
# ==========================================

def redirect_short(request, code):
    # 1. Look up inside the Render container's RAM first (~0.5ms)
    cache_key = f"short_url:{code}"
    long_url = cache.get(cache_key)
    
    if not long_url:
        # 2. Fallback to indexed DB if missing from RAM
        entry = get_object_or_404(ShortURL, short_code=code)
        long_url = entry.long_url
        # 3. Cache it so the next hits skip the DB entirely
        cache.set(cache_key, long_url, timeout=86400) # 24 Hours
        
    return redirect(long_url)


def redirect_short_url(request, shortcode):
    """Fallback if your urls.py routes to 'shortcode' instead of 'code'"""
    return redirect_short(request, code=shortcode)


# ==========================================
# 3. API ENDPOINTS
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



# Global application memory structures matching your automation configuration state
LIVE_AMAZON_COOKIES = {
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
    "ak_bmsc": "1949F7241193F3014A3CDCD62C1ED120~000000000000000000000000000000~YAAQvfXSF7QO1cSeAQAAZ9hGygCYNZpgZbOoTeVlUJNSiBbljnAYR16FKBwbNRJ1kEY68IXHk5JSlkPxD4BEz4zqkik6d1juv+1gr7zevmorOQ6EXoiV/flD64xxiA4sfNNumh5/mmIrSSv0Fe2Yq+FEQGPZdA5mNmjjhjqY/p608tGDaWZV5n+xI3sZPNuIQYp4uf9tp2eQt12VJcteQ5uU7plCAWcEH8cYYlB26HBPBvk5WfH/RekuYwAiiONeVTxCy52xBRy3HpH5yQmVBDeg0tZohQQWX6gycyXR9L0tsY9Cop38BDmXojwVhGNlEv7JGzhHtpt3vSwDohb7bwOpyDg26SCATx9XsoCVbQIpfXzJfTG4HarRCIofmD8CfSueJdwzeHaG3yZhUdGMb0eDDVnyFyHMSog4VDrwj2nsjTUSlHEWDizIYiflq3F858QJb4wZb1hASHGhSRVdA7HP40wVqgTQU9ALc0GAeDd4x",
    "bm_sv": "C325C8BC96CF5206474CF3AD0CA7160D~YAAQvfXSFxJ/1cSeAQAA4TZHygAX/kCbVlji+Tam9wITSIk+eHePnQimfvtyqPa2pDuiICFV3znSDhJ2NFbQbKoMcwrCnJ/uCeNjyxbEm766snO5HXyl2PGfmUgsS/ohOVk87u0kLoxLD9mK9Dvh/GB/z81Ap/8qYWPe9ysasyCRZPIqwn7AjyqGdlU+NTw7RpnK9C2j148M7Zjxs3EVuTvx5mbZuad5+9nU8YKbdl6lS1iwCnU9+2fv+hsomtit~1",
    "rxc": "AAnWe6HTxOPUNmSZT+8"
}

def clean_and_tag_url(url, tag):
    """Helper mimicking bot.py to structure cleanly into target payload format"""
    parsed = urlparse(url)
    query_params = parse_qs(parsed.query, keep_blank_values=True)
    # Remove junk keys if they exist
    if 's' in query_params:
        query_params.pop('s')
    query_params['tag'] = [tag]
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, urlencode(query_params, doseq=True), ''))

# ============================================================================
# NEW API: CREATE SHORTENED LINK WITH CUSTOM LOGIC
# ============================================================================
@api_view(["POST"])
def create_short_url(request):
    raw_url = request.data.get("url")
    tag = request.data.get("tag", "alena01-21")  # Fallback to defaults

    if not raw_url:
        return Response({"error": "URL parameter missing"}, status=400)

    # Clean raw Amazon query tracking configurations
    long_url = clean_and_tag_url(raw_url, tag)

    # Use existing memory tracking instance structure
    obj, created = ShortURL.objects.get_or_create(long_url=long_url)

    # Millisecond lookup logic implementation using local cache mapping
    cache_key = f"short_url:{obj.short_code}"
    cache.set(cache_key, obj.long_url, timeout=86400)

    return Response({
        "long_url": obj.long_url,
        "short_url": obj.short_url,
        "short_code": obj.short_code
    })

# ============================================================================
# NEW API: UPDATE SYSTEM SCRAPING COOKIES OVER NETWORKS ON THE FLY
# ============================================================================
@api_view(["POST"])
def update_amazon_cookies(request):
    global LIVE_AMAZON_COOKIES
    
    # Accept structural parameters matching your given template
    new_cookies = request.data
    if not new_cookies or not isinstance(new_cookies, dict):
        return Response({"error": "Invalid cookie map structure supplied"}, status=400)

    # Map keys directly to global active system parameters
    for key, val in new_cookies.items():
        # Ensure proper wrapping formatting constraints are respected
        if key in ["sid", "x-acbin"] and val and not val.startswith('"'):
            LIVE_AMAZON_COOKIES[key] = f'"{val}"'
        else:
            LIVE_AMAZON_COOKIES[key] = val

    return Response({
        "message": "System scraping configuration cookies updated successfully",
        "current_keys_cached": list(LIVE_AMAZON_COOKIES.keys())
    }, status=200)


from django.core.paginator import Paginator
from django.shortcuts import render
from .models import Product

def product_list(request):
    # 1. Fetch products efficiently using select_related
    products_list = Product.objects.select_related('link').all().order_by('-created_at')
    
    # 2. Slice items into batches of 8 for optimal mobile rendering speed
    paginator = Paginator(products_list, 8)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # 3. Check if JavaScript is requesting a background batch append
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render(request, 'products/product_cards_partial.html', {'page_obj': page_obj})
        
    return render(request, 'products/product_list.html', {'page_obj': page_obj})