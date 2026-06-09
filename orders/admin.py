from django.contrib import admin
from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ["unit_price"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "customer", "status", "created_at"]
    list_filter = ["status", "created_at"]
    search_fields = ["customer__username"]
    inlines = [OrderItemInline]
    readonly_fields = ["created_at", "updated_at"]
