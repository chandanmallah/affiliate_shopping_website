# serializers.py

from rest_framework import serializers
from .models import AmazonLink, Product

class AmazonLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmazonLink
        fields = ['id', 'product_url', 'title', 'slug', 'asin', 'added_at']
        read_only_fields = ['slug', 'added_at']

class ProductSerializer(serializers.ModelSerializer):
    link = AmazonLinkSerializer()

    class Meta:
        model = Product
        # Explicitly tracking operational presentation boundaries
        fields = ['id', 'link', 'description', 'image_url', 'title', 'source', 'category',
                  'price_display', 'mrp_display', 'discount_percentage', 'created_at']
        read_only_fields = ['created_at']

    def create(self, validated_data):
        link_data = validated_data.pop('link')
        amazon_link = AmazonLink.objects.create(**link_data)
        product = Product.objects.create(link=amazon_link, **validated_data)
        return product
    


