from django.shortcuts import render, get_object_or_404
from .models import Product
# views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .models import Product
from .serializers import ProductSerializer

from django.shortcuts import render

def add_product_page(request):
    return render(request, 'products/add_product.html')


def product_list(request):
    products = Product.objects.select_related('link').all().order_by('-created_at')
    return render(request, 'products/product_list.html', {'products': products})    

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

