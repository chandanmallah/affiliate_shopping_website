"""
Refresh Amazon product prices via the Creators/PA-API.

Place this file at:
    products/management/commands/update_price.py
(ensure products/management/__init__.py and
 products/management/commands/__init__.py exist)

Run it once every 24 hours (cron / Render cron job):
    python manage.py update_price

Behaviour:
  * For every Amazon product with an ASIN, fetch the current price.
  * If a fresh price is returned -> update price / MRP / discount.
  * If the item has NO buyable price -> CLEAR the price fields (so a stale
    price is never shown — required by the Associates Operating Agreement).
  * Safety: changes are staged and only written at the end in one transaction,
    and if too many calls fail in a row (an API outage / bad credentials) the
    run ABORTS and writes nothing, so an outage can't wipe every price.

Options:
    --sleep 1.1     seconds between API calls (respect the 1 TPS PA-API limit)
    --limit 0       only process N products (0 = all); useful for testing
    --dry-run       show what would change without writing to the DB
"""

import time
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone


# If a product's AmazonLink has no tag, fetch with this one (price is the same
# regardless of tag — the tag is only required by the API).
FALLBACK_TAG = "kuldeepsingh01-21"

# Abort (write nothing) if this many calls fail consecutively — almost always
# means the API is down or credentials are wrong, not that every item is sold out.
OUTAGE_ABORT_AFTER = 15


def _set_if_field(product, field_names, name, value):
    """Only set a field if the model actually has it (keeps this portable)."""
    if name in field_names:
        setattr(product, name, value)


class Command(BaseCommand):
    help = "Refresh Amazon prices (PA-API). Clears the price if none is available. Run every 24h."

    def add_arguments(self, parser):
        parser.add_argument("--sleep", type=float, default=1.1)
        parser.add_argument("--limit", type=int, default=0)
        parser.add_argument("--dry-run", action="store_true")

    def handle(self, *args, **opts):
        # Imported here so the module loads even if these move around.
        from products.models import Product
        from products.views import (fetch_product_from_creators_api,
                                    derive_amazon_category, bust_catalog_cache)

        field_names = {f.name for f in Product._meta.get_fields()}
        has_updated_at = "price_updated_at" in field_names

        qs = (Product.objects
              .select_related("link")
              .filter(source="amazon")
              .exclude(link__asin__isnull=True)
              .exclude(link__asin=""))
        if opts["limit"]:
            qs = qs[:opts["limit"]]

        products = list(qs)
        if not products:
            self.stdout.write("No Amazon products with an ASIN to refresh.")
            return

        # Group products by ASIN so each ASIN is fetched only once.
        by_asin = {}
        for p in products:
            by_asin.setdefault(p.link.asin, []).append(p)

        self.stdout.write(
            f"Refreshing {len(products)} product(s) across {len(by_asin)} ASIN(s)..."
        )

        staged = []          # (product, action, data) to apply at the end
        consecutive_fail = 0
        n_updated = n_cleared = n_failed = 0

        for asin, group in by_asin.items():
            tag = group[0].link.tag or FALLBACK_TAG
            data = None
            # one retry for transient hiccups
            for _ in range(2):
                try:
                    data = fetch_product_from_creators_api(asin, tag)
                except Exception as e:  # noqa
                    self.stderr.write(f"  {asin}: fetch error: {e}")
                    data = None
                if data is not None:
                    break
                time.sleep(opts["sleep"])

            has_price = bool(data and data.get("price_amount"))

            if data is None:
                # Couldn't reach / no response — treat as failure (outage guard).
                consecutive_fail += 1
                n_failed += 1
                if consecutive_fail >= OUTAGE_ABORT_AFTER:
                    self.stderr.write(self.style.ERROR(
                        f"Aborting: {consecutive_fail} consecutive failures "
                        f"(API outage or bad credentials). No changes written."
                    ))
                    return
                # No data and not an outage yet -> clear (no fresh price to show).
                for p in group:
                    staged.append((p, "clear", None))
                n_cleared += len(group)
            else:
                consecutive_fail = 0
                if has_price:
                    for p in group:
                        staged.append((p, "update", data))
                    n_updated += len(group)
                else:
                    # API responded but the item has no buyable offer -> clear.
                    for p in group:
                        staged.append((p, "clear", None))
                    n_cleared += len(group)

            time.sleep(opts["sleep"])

        # ---- apply staged changes ----
        if opts["dry_run"]:
            self.stdout.write(self.style.WARNING(
                f"[DRY RUN] would update {n_updated}, clear {n_cleared}, "
                f"failed {n_failed}. Nothing written."
            ))
            return

        now = timezone.now()
        with transaction.atomic():
            for product, action, data in staged:
                if action == "update":
                    # Price block
                    product.price_display = data.get("price", "")
                    product.price_amount = data.get("price_amount")
                    _set_if_field(product, field_names, "price_currency",
                                  data.get("price_currency") or "INR")
                    product.mrp_display = data.get("mrp_display", "")
                    product.mrp_amount = data.get("mrp_amount")
                    product.discount_percentage = data.get("discount_percentage")
                    _set_if_field(product, field_names, "savings_display",
                                  data.get("savings_display", ""))
                    _set_if_field(product, field_names, "savings_amount",
                                  data.get("savings_amount"))
                    # Everything else the API returned (refresh the whole record)
                    if data.get("title"):
                        product.title = data["title"]
                        if product.link and product.link.title != data["title"]:
                            product.link.title = data["title"]
                            product.link.save(update_fields=["title"])
                    if data.get("primary_image"):
                        product.image_url = data["primary_image"]
                    _set_if_field(product, field_names, "variant_images",
                                  data.get("all_images", []))
                    _set_if_field(product, field_names, "features",
                                  data.get("features", []))
                    _set_if_field(product, field_names, "overall_rank",
                                  data.get("overall_rank"))
                    _set_if_field(product, field_names, "overall_rank_context",
                                  data.get("overall_rank_context", ""))
                    _set_if_field(product, field_names, "category_rankings",
                                  data.get("category_rankings", []))
                    _cat = derive_amazon_category(data)
                    if _cat:
                        product.category = _cat
                else:  # clear
                    product.price_display = ""
                    product.price_amount = None
                    product.mrp_display = ""
                    product.mrp_amount = None
                    product.discount_percentage = None
                    _set_if_field(product, field_names, "savings_display", "")
                    _set_if_field(product, field_names, "savings_amount", None)

                if has_updated_at:
                    product.price_updated_at = now

                fields = ["price_display", "price_amount", "mrp_display",
                          "mrp_amount", "discount_percentage", "title", "image_url",
                          "category"]
                for extra in ("price_currency", "savings_display", "savings_amount",
                              "variant_images", "features", "overall_rank",
                              "overall_rank_context", "category_rankings",
                              "price_updated_at"):
                    if extra in field_names:
                        fields.append(extra)
                fields = [f for f in fields if f in field_names]
                product.save(update_fields=fields)

        bust_catalog_cache()
        self.stdout.write(self.style.SUCCESS(
            f"Done. Updated {n_updated}, cleared {n_cleared}, failed {n_failed}."
        ))