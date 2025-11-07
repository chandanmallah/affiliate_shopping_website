from django.shortcuts import render, get_object_or_404
from .models import Product
# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Product
from .serializers import ProductSerializer

from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from .models import ShortURL


def add_product_page(request):
    return render(request, 'products/add_product.html')


def product_list(request):
    products = Product.objects.select_related('link').all().order_by('-created_at')
    return render(request, 'products/product_list.html', {'products': products})   

from django.shortcuts import get_object_or_404, redirect
from .models import ShortURL

def redirect_short(request, code):
    entry = get_object_or_404(ShortURL, short_code=code)
    return redirect(entry.long_url) 


from .models import ShortURL

def redirect_short_url(request, shortcode):
    obj = get_object_or_404(ShortURL, shortcode=shortcode)
    return redirect(obj.long_url)

# def product_list(request):
#     products = Product.objects.all()
#     return render(request, 'products/product_list.html', {'products': products})

def product_detail(request, slug):
    product = get_object_or_404(Product, link__slug=slug)
    return render(request, 'products/product_detail.html', {'product': product})


class ProductListCreateAPIView(APIView):
    def get(self, request):
        products = Product.objects.select_related('link').all()
        serializer = ProductSerializer(products, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if serializer.is_valid():
            product = serializer.save()
            return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)




@api_view(["POST"])
def create_short_url(request):
    long_url = request.data.get("url")

    if not long_url:
        return Response({"error": "URL is required"}, status=400)

    # ✅ Return same short URL if exists
    obj, created = ShortURL.objects.get_or_create(long_url=long_url)

    return Response({
        "long_url": obj.long_url,
        "short_url": obj.short_url,
        "short_code": obj.short_code
    })