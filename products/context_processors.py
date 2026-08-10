
from django.conf import settings

_FALLBACK = {"name": "DealHunts", "lead": "DEAL", "tail": "HUNTS"}


def site_branding(request):
    host = request.get_host().split(":")[0].lower()
    if host.startswith("www."):
        host = host[4:]

    brands = getattr(settings, "SITE_BRANDS", {})
    brand = brands.get(host) or getattr(settings, "DEFAULT_SITE_BRAND", _FALLBACK)

    # Support email: use an explicit one from SITE_BRANDS if given, else derive
    # it from the current domain so cmaff.in shows support@cmaff.in automatically.
    support_email = brand.get("support_email") or f"support@{host}"

    # Logo file (lives in products/static/products/images/). Falls back to logo.png.
    logo_file = brand.get("logo", "logo.png")

    return {
        "site_name": brand.get("name", _FALLBACK["name"]),
        "site_name_lead": brand.get("lead", _FALLBACK["lead"]),
        "site_name_tail": brand.get("tail", _FALLBACK["tail"]),
        "site_domain": host,
        "site_support_email": support_email,
        "site_logo": f"products/images/{logo_file}",
    }