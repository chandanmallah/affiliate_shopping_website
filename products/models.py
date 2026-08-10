from django.db import models
from django.utils.text import slugify

from django.utils.crypto import get_random_string
from django.conf import settings


class AppConfiguration(models.Model):
    """
    A persistent cloud-safe Key-Value store to hold dynamic configurations
    like volatile Amazon session cookies across ephemeral container restarts.
    """
    key = models.CharField(max_length=255, unique=True)
    value = models.JSONField(default=dict)

    def __str__(self):
        return self.key
class AmazonLink(models.Model):
    # Free-text / URL fields use TextField (Postgres: unbounded, no perf cost)
    # so externally-sourced values can never overflow a column.
    product_url = models.TextField()
    title = models.TextField(blank=True)
    slug = models.SlugField(unique=True, blank=True)  # generated, stays short
    asin = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    # Affiliate tag this link was generated with. Combined with asin it gives a
    # distinct shareable page per (product, tag) so each bot keeps its own tag.
    tag = models.CharField(max_length=100, blank=True, db_index=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title or "product")
            base_slug = base_slug[:3].rstrip('-')
            unique_suffix = get_random_string(3)
            self.slug = f"{base_slug}-{unique_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or self.product_url

from django.utils import timezone
import random
from decimal import Decimal


def _seed_views():
    return random.randint(60, 800)


# ─────────────────────────────────────────────────────────────
# AUTO RATING + AUTO REVIEW HELPERS
# ─────────────────────────────────────────────────────────────

def _seed_rating():
    """A believable headline star rating between 4.3 and 4.9 (one decimal)."""
    return Decimal(random.choice(["4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9"]))


def _seed_rating_count():
    """A small, believable number of ratings (3–15) for a fresh listing."""
    return random.randint(3, 15)


_REVIEW_OPENERS = [
    "Honestly exceeded my expectations.",
    "Really happy with this purchase.",
    "Great value for the price.",
    "Does exactly what it promises.",
    "Solid quality — would buy again.",
    "Impressed with the build and finish.",
    "Genuinely a smart buy.",
]
_REVIEW_BODIES = [
    "Delivery was quick and the packaging was secure. Been using it for a couple of weeks now and it's holding up really well.",
    "Works exactly as described and feels premium for the price point. No complaints so far.",
    "Setup was straightforward and it fit my needs perfectly. Already recommended it to friends and family.",
    "The quality is noticeably better than similar options I've tried before. Money well spent.",
    "Everything about it feels well thought out and it's been doing the job without any issues.",
    "Bought it during a sale and it turned out to be a fantastic deal. Very satisfied with the value.",
]
_REVIEW_CLOSERS = [
    "Definitely recommend it.",
    "Would buy again without hesitation.",
    "Five stars from me.",
    "Very satisfied overall.",
    "Great pick if you're on the fence.",
]
_REVIEW_NAMES = [
    "Rahul S.", "Priya M.", "Amit K.", "Sneha R.", "Vikram J.",
    "Ananya P.", "Karthik N.", "Divya S.", "Rohan G.", "Meera T.",
    "Arjun V.", "Pooja B.", "Sahil D.", "Nisha K.", "Manish A.",
    "Ishita C.", "Aditya R.", "Neha L.", "Varun M.", "Shreya D.",
]


def build_auto_review(title="", brand="", category="", rating=4.6):
    """Compose a short, generic-but-natural review + a plausible author name."""
    text = "{} {} {}".format(
        random.choice(_REVIEW_OPENERS),
        random.choice(_REVIEW_BODIES),
        random.choice(_REVIEW_CLOSERS),
    )
    return random.choice(_REVIEW_NAMES), text


class Product(models.Model):
    """
    Latest known full detail for a product, one row per AmazonLink.
    Free-text fields are TextField so we never have to guess a max length.
    """
    link = models.OneToOneField(AmazonLink, on_delete=models.CASCADE, related_name="product")
    description = models.TextField(blank=True)

    # ---- Platform / category (drives homepage sections + strip filtering) ---
    SOURCE_CHOICES = [
        ("amazon", "Amazon"),
        ("flipkart", "Flipkart"),
        ("myntra", "Myntra"),
        ("ajio", "Ajio"),
    ]
    source = models.CharField(
        max_length=20, choices=SOURCE_CHOICES, default="amazon", db_index=True
    )
    category = models.TextField(blank=True, db_index=True)

    # ---- Images ---------------------------------------------------------
    image_url = models.TextField(blank=True)  # Primary Image
    image_width = models.PositiveIntegerField(null=True, blank=True)
    image_height = models.PositiveIntegerField(null=True, blank=True)
    variant_images = models.JSONField(default=list, blank=True)

    # ---- Title / Brand / Classification ---------------------------------
    title = models.TextField(blank=True)
    brand = models.TextField(blank=True)
    manufacturer = models.TextField(blank=True)
    contributors = models.JSONField(default=list, blank=True)

    product_group = models.TextField(blank=True)
    binding = models.TextField(blank=True)

    # ---- Manufacture info -----------------------------------------------
    item_part_number = models.TextField(blank=True)
    model_number = models.TextField(blank=True)
    warranty = models.TextField(blank=True)

    # ---- Product info / dimensions --------------------------------------
    color = models.TextField(blank=True)
    size = models.TextField(blank=True)
    unit_count = models.TextField(blank=True)

    dimension_height = models.TextField(blank=True)
    dimension_length = models.TextField(blank=True)
    dimension_width = models.TextField(blank=True)
    dimension_weight = models.TextField(blank=True)

    # ---- Features (bullet points) ---------------------------------------
    features = models.JSONField(default=list, blank=True)

    # ---- Customer reviews (from Amazon PA-API, may be blank) ------------
    star_rating = models.TextField(blank=True)
    review_count = models.TextField(blank=True)
    bought_past_month = models.TextField(blank=True)

    # ---- Site rating + auto review (always present) ---------------------
    # `rating` is the headline star value shown on cards + detail page.
    # It is seeded to 4.3–4.9 and stays fixed for the row's lifetime.
    rating = models.DecimalField(max_digits=2, decimal_places=1, default=_seed_rating)
    rating_count = models.PositiveIntegerField(default=_seed_rating_count)
    auto_review = models.TextField(blank=True)
    auto_review_author = models.CharField(max_length=80, blank=True)

    # ---- Parent ASIN / rankings -----------------------------------------
    parent_asin = models.CharField(max_length=10, blank=True)

    overall_rank = models.PositiveIntegerField(null=True, blank=True)
    overall_rank_context = models.TextField(blank=True)
    category_rankings = models.JSONField(default=list, blank=True)

    # ---- Offer / pricing -------------------------------------------------
    price_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_display = models.TextField(blank=True)
    price_currency = models.TextField(blank=True)

    mrp_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    mrp_display = models.TextField(blank=True)
    mrp_label = models.TextField(blank=True)

    discount_percentage = models.PositiveIntegerField(null=True, blank=True)
    savings_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    savings_display = models.TextField(blank=True)

    condition = models.TextField(blank=True)

    availability_message = models.TextField(blank=True)
    availability_type = models.TextField(blank=True)

    merchant_name = models.TextField(blank=True)
    merchant_id = models.TextField(blank=True)

    is_buy_box_winner = models.BooleanField(null=True, blank=True)
    listing_type = models.TextField(blank=True)

    deal_type = models.TextField(blank=True)
    deal_end_time = models.DateTimeField(null=True, blank=True)

    loyalty_points = models.PositiveIntegerField(null=True, blank=True)

    raw_extra = models.JSONField(default=dict, blank=True)

    # ---- Bookkeeping ----------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    views = models.PositiveIntegerField(default=_seed_views)
    date_posted = models.DateTimeField(default=timezone.now)

    def save(self, *args, **kwargs):
        # Generate a one-time auto review the first time the row is saved.
        if not self.auto_review:
            author, text = build_auto_review(
                self.title or "", self.brand or "", self.category or "",
                float(self.rating or Decimal("4.6")),
            )
            self.auto_review = text
            if not self.auto_review_author:
                self.auto_review_author = author
        super().save(*args, **kwargs)

    # ---- Rating display helpers ----------------------------------------
    @property
    def rating_pct(self):
        """Star-fill percentage (0–100) for the seeded headline rating."""
        return round(float(self.rating or 0) / 5 * 100, 1)

    @property
    def approved_reviews(self):
        return self.reviews.filter(is_approved=True)

    @property
    def average_rating(self):
        """Seeded rating blended with real user reviews (seed = large sample)."""
        base_n = self.rating_count or 0
        ur = list(self.approved_reviews)
        if not ur:
            return round(float(self.rating or 0), 1)
        base_sum = float(self.rating or 0) * base_n
        return round((base_sum + sum(r.rating for r in ur)) / (base_n + len(ur)), 1)

    @property
    def total_rating_count(self):
        return (self.rating_count or 0) + self.approved_reviews.count()

    def __str__(self):
        return self.title or self.link.title


class Review(models.Model):
    """A review from a site member, shown on the product page."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    author = models.CharField(max_length=80)
    email = models.EmailField(blank=True)                  # collected, never shown publicly
    rating = models.PositiveSmallIntegerField(default=5)   # 1..5
    title = models.CharField(max_length=140, blank=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_approved = models.BooleanField(default=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.author} · {self.rating}star · {self.product_id}"

    @property
    def rating_pct(self):
        return round(self.rating / 5 * 100, 1)


class ProductSnapshot(models.Model):
    """
    One row per check_asin() run for a given product — price/availability/rank
    history over time.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="snapshots")

    checked_at = models.DateTimeField(auto_now_add=True, db_index=True)

    price_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_display = models.TextField(blank=True)

    mrp_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    mrp_display = models.TextField(blank=True)

    discount_percentage = models.PositiveIntegerField(null=True, blank=True)
    savings_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    availability_message = models.TextField(blank=True)
    availability_type = models.TextField(blank=True)

    merchant_name = models.TextField(blank=True)
    is_buy_box_winner = models.BooleanField(null=True, blank=True)

    star_rating = models.TextField(blank=True)
    review_count = models.TextField(blank=True)
    bought_past_month = models.TextField(blank=True)

    overall_rank = models.PositiveIntegerField(null=True, blank=True)

    deal_type = models.TextField(blank=True)
    deal_end_time = models.DateTimeField(null=True, blank=True)


    class Meta:
        ordering = ["-checked_at"]

    def __str__(self):
        return f"{self.product} @ {self.checked_at:%Y-%m-%d %H:%M}"


class ShortURL(models.Model):
    long_url = models.TextField(db_index=True)   # not unique: one long URL may have many codes
    short_code = models.CharField(max_length=10, unique=True, db_index=True)  # generated
    short_url = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.short_code:
            self.short_code = get_random_string(7)

        domain = getattr(settings, "SHORTENER_DOMAIN", "https://amozn.in")
        self.short_url = f"{domain}/{self.short_code}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.short_url