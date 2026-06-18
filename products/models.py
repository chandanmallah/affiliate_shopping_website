# from django.db import models
# from django.utils.text import slugify
# from django.utils.crypto import get_random_string
# from django.db import models
# from django.utils.crypto import get_random_string
# from django.conf import settings

# class AppConfiguration(models.Model):
#     """
#     A persistent cloud-safe Key-Value store to hold dynamic configurations 
#     like volatile Amazon session cookies across ephemeral container restarts.
#     """
#     key = models.CharField(max_length=255, unique=True)
#     value = models.JSONField(default=dict)

#     def __str__(self):
#         return self.key

# class AmazonLink(models.Model):
#     # Changed max_length from 500 to 2000
#     product_url = models.URLField(max_length=2000) 
#     title = models.CharField(max_length=200, blank=True)
#     slug = models.SlugField(unique=True, blank=True)
#     added_at = models.DateTimeField(auto_now_add=True)

#     def save(self, *args, **kwargs):
#         if not self.slug:
#             base_slug = slugify(self.title or "product")
#             unique_suffix = get_random_string(6)
#             self.slug = f"{base_slug}-{unique_suffix}"
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return self.title or self.product_url

# class Product(models.Model):
#     link = models.OneToOneField(AmazonLink, on_delete=models.CASCADE)
#     description = models.TextField(blank=True)
#     # Changed max_length to 2000 to match just in case
#     image_url = models.URLField(max_length=2000, blank=True)  
#     created_at = models.DateTimeField(auto_now_add=True)

#     def __str__(self):
#         return self.link.title


# class ShortURL(models.Model):
#     # Changed max_length from 500 to 2000
#     long_url = models.URLField(max_length=2000, unique=True)  
#     short_code = models.CharField(max_length=10, unique=True, db_index=True)
#     # Changed max_length from 300 to 1000
#     short_url = models.URLField(max_length=1000, blank=True)  
#     created_at = models.DateTimeField(auto_now_add=True)

#     def save(self, *args, **kwargs):
#         if not self.short_code:
#             self.short_code = get_random_string(7)

#         domain = getattr(settings, "SHORTENER_DOMAIN", "https://amozn.in")
#         self.short_url = f"{domain}/{self.short_code}"
#         super().save(*args, **kwargs)
#     def __str__(self):
#         return self.short_url



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
    product_url = models.URLField(max_length=2000)
    title = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(unique=True, blank=True) # Defaults to max_length=50 in DB
    asin = models.CharField(max_length=10, null=True, blank=True, db_index=True)
    # Affiliate tag this link was generated with. Combined with asin it gives a
    # distinct shareable page per (product, tag) so each bot keeps its own tag.
    tag = models.CharField(max_length=100, blank=True, db_index=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            # 1. Generate the raw slug text from the title
            base_slug = slugify(self.title or "product")

            # 2. Truncate the base to 3 chars (and drop any trailing hyphen)
            base_slug = base_slug[:3].rstrip('-')

            # 3. Combine with a random suffix (3 + 1 + 3 = 7 chars max, well under 50)
            unique_suffix = get_random_string(3)
            self.slug = f"{base_slug}-{unique_suffix}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or self.product_url

class Product(models.Model):
    """
    Latest known full detail for a product, one row per AmazonLink.
    Populated/refreshed by monitor.py's check_asin() -> build_snapshot().
    Every column here maps to a specific field monitor.py already
    extracts from the Amazon API response (see print_product /
    build_snapshot) or from the Selenium review scrape.
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
    # Normalized category label used by the homepage category strip filter.
    # For Amazon this is auto-derived from the browse-node root; for manual
    # uploads it is chosen from the same strip label list.
    category = models.CharField(max_length=120, blank=True, db_index=True)

    # ---- Images ---------------------------------------------------------
    image_url = models.URLField(max_length=2000, blank=True) # Primary Image
    image_width = models.PositiveIntegerField(null=True, blank=True)
    image_height = models.PositiveIntegerField(null=True, blank=True)
    
    # NEW FIELD: Store multiple image URLs here as a list -> ["url1", "url2", ...]
    variant_images = models.JSONField(default=list, blank=True)  

    # ---- Title / Brand / Classification (itemInfo.*) ---------------------
    title = models.CharField(max_length=500, blank=True)
    brand = models.CharField(max_length=255, blank=True)
    manufacturer = models.CharField(max_length=255, blank=True)
    contributors = models.JSONField(default=list, blank=True)  

    product_group = models.CharField(max_length=255, blank=True) # Category/Product Group
    binding = models.CharField(max_length=255, blank=True)    

    # ---- Manufacture info --------------------------------------------------
    item_part_number = models.CharField(max_length=255, blank=True)
    model_number = models.CharField(max_length=255, blank=True)
    warranty = models.TextField(blank=True)

    # ---- Product info / dimensions -----------------------------------------
    color = models.CharField(max_length=255, blank=True)
    size = models.CharField(max_length=255, blank=True)
    unit_count = models.CharField(max_length=100, blank=True)

    dimension_height = models.CharField(max_length=50, blank=True)
    dimension_length = models.CharField(max_length=50, blank=True)
    dimension_width = models.CharField(max_length=50, blank=True)
    dimension_weight = models.CharField(max_length=50, blank=True)

    # ---- Features (bullet points) -------------------------------------------
    features = models.JSONField(default=list, blank=True)  # ["feature 1", "feature 2", ...]

    # ---- Customer reviews (Selenium-scraped, live) ---------------------------
    star_rating = models.CharField(max_length=20, blank=True)        # e.g. "4.3"
    review_count = models.CharField(max_length=50, blank=True)       # e.g. "1,204 ratings"
    bought_past_month = models.CharField(max_length=100, blank=True) # e.g. "200+ bought in past month"

    # ---- Parent ASIN / rankings ------------------------------------------------
    parent_asin = models.CharField(max_length=10, blank=True)

    overall_rank = models.PositiveIntegerField(null=True, blank=True)
    overall_rank_context = models.CharField(max_length=255, blank=True)
    category_rankings = models.JSONField(default=list, blank=True)
    # [{"node_id": "...", "name": "...", "rank": 123, "is_root": false, "path": "A > B > C"}]

    # ---- Offer / pricing (current/latest listing) -----------------------------
    price_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_display = models.CharField(max_length=50, blank=True)   # e.g. "₹1,299.00"
    price_currency = models.CharField(max_length=10, blank=True)  # e.g. "INR"

    mrp_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    mrp_display = models.CharField(max_length=50, blank=True)
    mrp_label = models.CharField(max_length=100, blank=True)  # saving_basis_type_label, usually "MRP"

    discount_percentage = models.PositiveIntegerField(null=True, blank=True)
    savings_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    savings_display = models.CharField(max_length=50, blank=True)

    condition = models.CharField(max_length=100, blank=True)

    availability_message = models.CharField(max_length=255, blank=True)
    availability_type = models.CharField(max_length=100, blank=True)

    merchant_name = models.CharField(max_length=255, blank=True)
    merchant_id = models.CharField(max_length=255, blank=True)

    is_buy_box_winner = models.BooleanField(null=True, blank=True)
    listing_type = models.CharField(max_length=100, blank=True)

    deal_type = models.CharField(max_length=100, blank=True)
    deal_end_time = models.DateTimeField(null=True, blank=True)

    loyalty_points = models.PositiveIntegerField(null=True, blank=True)

    raw_extra = models.JSONField(default=dict, blank=True)

    # ---- Bookkeeping --------------------------------------------------------
    created_at = models.DateTimeField(auto_now_add=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.title or self.link.title


class ProductSnapshot(models.Model):
    """
    One row per check_asin() run for a given product — full history of
    price/availability/rank/review changes over time. Mirrors the same
    fields as Product's "current state" columns, minus the static
    catalog info (title, features, dimensions, etc.) that doesn't
    meaningfully change run to run.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="snapshots")

    checked_at = models.DateTimeField(auto_now_add=True, db_index=True)

    price_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_display = models.CharField(max_length=50, blank=True)

    mrp_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    mrp_display = models.CharField(max_length=50, blank=True)

    discount_percentage = models.PositiveIntegerField(null=True, blank=True)
    savings_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    availability_message = models.CharField(max_length=255, blank=True)
    availability_type = models.CharField(max_length=100, blank=True)

    merchant_name = models.CharField(max_length=255, blank=True)
    is_buy_box_winner = models.BooleanField(null=True, blank=True)

    star_rating = models.CharField(max_length=20, blank=True)
    review_count = models.CharField(max_length=50, blank=True)
    bought_past_month = models.CharField(max_length=100, blank=True)

    overall_rank = models.PositiveIntegerField(null=True, blank=True)

    deal_type = models.CharField(max_length=100, blank=True)
    deal_end_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-checked_at"]

    def __str__(self):
        return f"{self.product} @ {self.checked_at:%Y-%m-%d %H:%M}"


class ShortURL(models.Model):
    # Changed max_length from 500 to 2000
    long_url = models.URLField(max_length=2000, unique=True)
    short_code = models.CharField(max_length=10, unique=True, db_index=True)
    # Changed max_length from 300 to 1000
    short_url = models.URLField(max_length=1000, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.short_code:
            self.short_code = get_random_string(7)

        domain = getattr(settings, "SHORTENER_DOMAIN", "https://amozn.in")
        self.short_url = f"{domain}/{self.short_code}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.short_url