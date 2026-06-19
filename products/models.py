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

    # ---- Customer reviews -----------------------------------------------
    star_rating = models.TextField(blank=True)
    review_count = models.TextField(blank=True)
    bought_past_month = models.TextField(blank=True)

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

    def __str__(self):
        return self.title or self.link.title


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
    long_url = models.TextField(unique=True)
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