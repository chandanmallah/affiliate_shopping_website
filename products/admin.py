from django.contrib import admin

from .models import Product, Review, AmazonLink


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("author", "email", "rating", "product", "is_approved", "created_at")
    list_filter = ("is_approved", "rating", "created_at")
    search_fields = ("author", "email", "title", "body")
    list_editable = ("is_approved",)          # tick/untick to moderate quickly
    actions = ["approve_reviews", "hide_reviews"]

    @admin.action(description="Approve selected reviews")
    def approve_reviews(self, request, queryset):
        queryset.update(is_approved=True)

    @admin.action(description="Hide selected reviews")
    def hide_reviews(self, request, queryset):
        queryset.update(is_approved=False)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "source", "rating", "rating_count", "views", "created_at")
    list_filter = ("source", "created_at")
    search_fields = ("title", "link__title", "link__asin", "link__tag")