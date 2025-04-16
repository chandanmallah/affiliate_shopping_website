# serializers.py
from rest_framework import serializers
from .models import AmazonLink, Product

class AmazonLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = AmazonLink
        fields = ['id', 'product_url', 'title', 'slug', 'added_at']
        read_only_fields = ['slug', 'added_at']

class ProductSerializer(serializers.ModelSerializer):
    link = AmazonLinkSerializer()

    class Meta:
        model = Product
        fields = ['id', 'link', 'description', 'image_url', 'created_at']
        read_only_fields = ['created_at']

    def create(self, validated_data):
        link_data = validated_data.pop('link')
        amazon_link = AmazonLink.objects.create(**link_data)
        product = Product.objects.create(link=amazon_link, **validated_data)
        return product
