from django.urls import path
from . import views
from . import auth_views
from .views import (
    ProductListCreateAPIView,
    add_product_page,
    product_detail_api,
    create_short_url,
    redirect_short,
    EnforceCatalogRetentionAPIView,
)

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('favicon.ico', views.favicon, name='favicon'),
    path('product/<slug:slug>/', views.product_detail, name='product_detail'),

    path('show-data/', views.show_data_page, name='show-data-page'),

    # ──────────────────────────────────────────────────────────────
    # MEMBER AUTH  (must stay ABOVE the catch-all redirect rule below)
    # ──────────────────────────────────────────────────────────────
    path('accounts/login/',  auth_views.member_login,  name='login'),
    path('accounts/signup/', auth_views.member_signup, name='signup'),
    path('accounts/logout/', auth_views.member_logout, name='logout'),

    path('api/products/', views.ProductListCreateAPIView.as_view(), name='product-list-create'),
    path('api/products/<slug:slug>/detail/', product_detail_api, name='product-detail-api'),
    path('add-product/', views.add_product_page, name='add-product-page'),

    # Staff-only manual upload (Amazon / Flipkart / Myntra / Ajio).
    # Gated by the Django admin login via @staff_member_required.
    path('upload/', views.manual_add_product, name='manual-add-product'),

    # Form endpoints
    path("api/shorten/", views.create_short_url),
    path("api/cookies/update/", views.update_amazon_cookies),

    # Affiliate link converter (UNLISTED — no nav shortcut; visit directly)
    path('convert/', views.affiliate_converter, name='affiliate-converter'),
    path('api/convert/', views.convert_affiliate_link, name='api-convert'),
    path('api/convert-message/', views.convert_message, name='api-convert-message'),
    path('api/products/cleanup/', EnforceCatalogRetentionAPIView.as_view(), name='api-catalog-cleanup'),
    path('privacy-policy/', views.privacy_policy, name='privacy-policy'),

    path('terms/',   views.terms,   name='terms'),
    path('contact/', views.contact, name='contact'),    

    # Fast Redirect Engine Rule  (catch-all — keep this LAST)
    path("<str:code>/", views.redirect_short, name='redirect'),
]