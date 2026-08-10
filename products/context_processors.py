"""
Per-domain branding for templates.

Register this in settings.py under TEMPLATES → OPTIONS → context_processors:

    'products.context_processors.site_branding',

Then configure the brands (also in settings.py):

    SITE_BRANDS = {
        "dealhunts.in": {"name": "DealHunts", "lead": "DEAL", "tail": "HUNTS"},
        "cmaff.in":     {"name": "CMAFF",     "lead": "CM",   "tail": "AFF"},
    }
    DEFAULT_SITE_BRAND = {"name": "DealHunts", "lead": "DEAL", "tail": "HUNTS"}

Templates then get:
    {{ site_name }}        -> "DealHunts" / "CMAFF"   (use in prose & titles)
    {{ site_name_lead }}   -> "DEAL" / "CM"           (first half of the two-tone logo)
    {{ site_name_tail }}   -> "HUNTS" / "AFF"         (highlighted half of the logo)
    {{ site_domain }}      -> "dealhunts.in" / "cmaff.in"
"""

from django.conf import settings

_FALLBACK = {"name": "DealHunts", "lead": "DEAL", "tail": "HUNTS"}


def site_branding(request):
    host = request.get_host().split(":")[0].lower()
    if host.startswith("www."):
        host = host[4:]

    brands = getattr(settings, "SITE_BRANDS", {})
    brand = brands.get(host) or getattr(settings, "DEFAULT_SITE_BRAND", _FALLBACK)

    return {
        "site_name": brand.get("name", _FALLBACK["name"]),
        "site_name_lead": brand.get("lead", _FALLBACK["lead"]),
        "site_name_tail": brand.get("tail", _FALLBACK["tail"]),
        "site_domain": host,
    }