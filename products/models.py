from django.db import models
from django.utils.text import slugify
from django.utils.crypto import get_random_string
from django.db import models
from django.utils.crypto import get_random_string
from django.conf import settings

class AmazonLink(models.Model):
    product_url = models.URLField(max_length=500)
    title = models.CharField(max_length=200, blank=True)
    slug = models.SlugField(unique=True, blank=True)
    added_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title or "product")
            unique_suffix = get_random_string(6)
            self.slug = f"{base_slug}-{unique_suffix}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or self.product_url

class Product(models.Model):
    link = models.OneToOneField(AmazonLink, on_delete=models.CASCADE)
    description = models.TextField(blank=True)
    image_url = models.URLField(blank=True)  # ✅ New field
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.link.title


class ShortURL(models.Model):
    long_url = models.URLField(max_length=500, unique=True)  # ✅ no duplicates
    short_code = models.CharField(max_length=10, unique=True)
    short_url = models.URLField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Generate new short code only for new entries
        if not self.short_code:
            self.short_code = get_random_string(7)

        # Final short URL
        domain = getattr(settings, "SHORTENER_DOMAIN", "https://www.amozn.in")
        self.short_url = f"{domain}/{self.short_code}"

        super().save(*args, **kwargs)

    def __str__(self):
        return self.short_url