"""
ONE-TIME seed for existing deals:
  * gives each existing Product a dummy view count, and
  * a random "posted" date within the CURRENT month, up to a cutoff day
    (default 23). New deals created afterwards keep their real date_posted
    (defaults to now) and their own dummy view base.

Place at: products/management/commands/seed_views_dates.py
Run ONCE, right after adding the `views` and `date_posted` model fields and
migrating, and BEFORE you start posting new deals:

    python manage.py seed_views_dates --confirm

Options:
    --confirm            required safety flag (prevents accidental re-runs)
    --min-views 60       lowest dummy view count
    --max-views 800      highest dummy view count
    --day-cutoff 23      random dates fall on day 1..cutoff of this month
    --only-empty         only seed products that still look unseeded
"""

import random
from datetime import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone


class Command(BaseCommand):
    help = "One-time: seed existing deals with dummy views + random current-month dates."

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true")
        parser.add_argument("--min-views", type=int, default=60)
        parser.add_argument("--max-views", type=int, default=800)
        parser.add_argument("--day-cutoff", type=int, default=23)
        parser.add_argument("--only-empty", action="store_true",
                            help="skip products that already have views > 0")

    def handle(self, *args, **opts):
        from products.models import Product

        if not opts["confirm"]:
            raise CommandError(
                "Refusing to run without --confirm. This rewrites dates/views on "
                "existing products and is meant to run only once."
            )

        now = timezone.localtime()
        year, month = now.year, now.month
        cutoff = max(1, min(opts["day_cutoff"], 28))
        lo, hi = opts["min_views"], opts["max_views"]

        qs = Product.objects.all()
        if opts["only_empty"]:
            qs = qs.filter(views=0)

        n = 0
        for p in qs.iterator():
            day = random.randint(1, cutoff)
            hour = random.randint(8, 22)
            minute = random.randint(0, 59)
            naive = datetime(year, month, day, hour, minute)
            p.date_posted = timezone.make_aware(naive)
            p.views = random.randint(lo, hi)
            p.save(update_fields=["date_posted", "views"])
            n += 1

        # Refresh the homepage cache if your project exposes the helper.
        try:
            from products.views import bust_catalog_cache
            bust_catalog_cache()
        except Exception:
            pass

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {n} product(s): views {lo}-{hi}, dates "
            f"{year}-{month:02d}-01 .. {year}-{month:02d}-{cutoff:02d}."
        ))