from django.urls import path
from . import views
from .views import ProductListCreateAPIView
from .views import add_product_page
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('api/products/', ProductListCreateAPIView.as_view(), name='product-list-create'),
    path('add-product/', add_product_page, name='add-product-page'),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'products' / 'static')