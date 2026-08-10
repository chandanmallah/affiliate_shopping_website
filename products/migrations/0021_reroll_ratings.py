from django.db import migrations
import random
from decimal import Decimal


def reroll(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    ratings = ["4.3", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9"]
    for p in Product.objects.all().iterator():
        p.rating = Decimal(random.choice(ratings))   # random 4.3–4.9
        p.rating_count = random.randint(3, 13)        # random 3–13
        p.save(update_fields=["rating", "rating_count"])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0020_review_email"),
    ]

    operations = [
        migrations.RunPython(reroll, noop),
    ]