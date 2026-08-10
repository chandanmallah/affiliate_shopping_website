"""
Re-roll ratings + counts for EVERY product already in the database.

WHY: `migrate` stamps all existing rows with a single default value (they all
show the same 4.9 / same count). New products get their own random values, but
old rows need this one-time fix. Run it whenever you change the rating/count
ranges too.

RUN ONCE from your project root:

    python manage.py shell < backfill_ratings.py
"""

import os
import sys
import datetime
import time
import re
from decimal import Decimal

# ============================================================
# INITIALIZE DJANGO ENVIRONMENT (Prevents Duplicate Registry)
# ============================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(BASE_DIR)
a= os.environ  # <-- Verify this matches your folder name
print(a)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "myproject.settings") 

from products.models import Product, _seed_rating, _seed_rating_count, build_auto_review
from products.models import AmazonLink, Product, ProductSnapshot  # Absolute import from app namespace

updated = 0
samples = []

for p in Product.objects.all().iterator():
    p.rating = _seed_rating()              # random 4.3-4.9
    p.rating_count = _seed_rating_count()  # random 3-15

    if not p.auto_review:
        author, text = build_auto_review(
            p.title or "", p.brand or "", p.category or "", float(p.rating)
        )
        p.auto_review = text
        p.auto_review_author = author

    p.save(update_fields=["rating", "rating_count", "auto_review", "auto_review_author"])
    updated += 1
    if len(samples) < 8:
        samples.append(f"  {p.rating} stars  ({p.rating_count} ratings)  - {(p.title or p.link.title)[:40]}")

print(f"\nRe-rolled {updated} products.")
print("Sample of what they look like now:")
print("\n".join(samples))