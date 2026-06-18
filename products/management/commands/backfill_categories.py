"""
One-time backfill: populate Product.category (the flat column the homepage
category strip filters on) for existing Amazon products, derived from the
browse-node breadcrumb already stored in Product.category_rankings.

Place this file at:
    products/management/commands/backfill_categories.py

Then run:
    python manage.py backfill_categories          # apply changes
    python manage.py backfill_categories --dry-run # preview only
"""

from django.core.management.base import BaseCommand
from products.models import Product


def derive_department(rankings):
    """Return the department label (top of the breadcrumb) for a product."""
    rankings = rankings or []

    # 1. Explicit root node.
    root = next((r for r in rankings if r.get("is_root") and r.get("name")), None)
    if root:
        return root["name"].strip()

    # 2. First segment of the longest breadcrumb path.
    best_path = ""
    for r in rankings:
        p = (r.get("path") or "")
        if len(p) > len(best_path):
            best_path = p
    if best_path:
        return best_path.split(" > ")[0].strip()

    # 3. Last-resort leaf fallback.
    if rankings and rankings[0].get("name"):
        return rankings[0]["name"].strip()
    return ""


class Command(BaseCommand):
    help = "Backfill Product.category for existing Amazon products from category_rankings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        updated = 0
        skipped = 0

        qs = Product.objects.filter(source="amazon")
        self.stdout.write(f"Scanning {qs.count()} Amazon products...\n")

        for p in qs.iterator():
            dept = derive_department(p.category_rankings)
            if not dept:
                skipped += 1
                continue
            if p.category == dept:
                continue

            self.stdout.write(f"  #{p.id}: '{p.category}' -> '{dept}'")
            if not dry_run:
                p.category = dept
                p.save(update_fields=["category"])
            updated += 1

        # Summary of distinct categories now present.
        cats = sorted(
            {c for c in Product.objects.values_list("category", flat=True) if c}
        )

        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.WARNING(f"DRY RUN — would update {updated} product(s)."))
        else:
            self.stdout.write(self.style.SUCCESS(f"Updated {updated} product(s)."))
        if skipped:
            self.stdout.write(f"{skipped} product(s) had no usable category data (skipped).")
        self.stdout.write("\nDistinct categories now in the DB:")
        for c in cats:
            self.stdout.write(f"  - {c}")
        self.stdout.write(
            "\nEach value above must match a strip label closely (icontains). "
            "Add any missing departments to STRIP_CATEGORIES in views.py."
        )