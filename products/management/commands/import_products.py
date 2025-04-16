import json
from django.core.management.base import BaseCommand
from products.models import AmazonLink, Product

class Command(BaseCommand):
    help = 'Import products from a JSON file'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str)

    def handle(self, *args, **kwargs):
        json_file = kwargs['json_file']
        with open(json_file, 'r') as f:
            data = json.load(f)

        for item in data:
            link, _ = AmazonLink.objects.get_or_create(
                product_url=item['product_url'],
                defaults={'title': item.get('title', '')}
            )
            Product.objects.get_or_create(
                link=link,
                defaults={
                    'description': item.get('description', ''),
                    'image_url': item.get('image_url', '')
                }
            )

        self.stdout.write(self.style.SUCCESS('Products imported successfully'))

