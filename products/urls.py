from django.urls import path
from . import views
from .views import ProductListCreateAPIView
from .views import add_product_page
from django.conf import settings
from django.conf.urls.static import static

from .views import create_short_url, redirect_short
from django.urls import path, re_path
from .views import redirect_short_url
# from .views import wipe_database


urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),
    path('api/products/', views.ProductListCreateAPIView.as_view(), name='product-list-create'),
    path('add-product/', views.add_product_page, name='add-product-page'),
    
    # Form endpoints
    path("api/shorten/", views.create_short_url),
    path("api/cookies/update/", views.update_amazon_cookies), # Cookie loader sync target
    
    # Fast Redirect Engine Rule 
    path("<str:code>/", views.redirect_short, name='redirect'),    
]    

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / 'products' / 'static')
