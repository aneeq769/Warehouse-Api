from decimal import Decimal
from django.db import transaction
from django.db.models import F
from rest_framework import serializers

from products.models import Product
from .models import Order, OrderItem


# ── Read serializers ─────────────────────────────────────────────────────────

class OrderItemReadSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="product.id", read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    product_sku = serializers.CharField(source="product.sku", read_only=True)
    line_total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_id",
            "product_name",
            "product_sku",
            "quantity",
            "unit_price",
            "line_total",
        ]

    def get_line_total(self, obj: OrderItem) -> Decimal:
        return obj.unit_price * obj.quantity


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()
    customer_username = serializers.CharField(
        source="customer.username", read_only=True
    )

    class Meta:
        model = Order
        fields = [
            "id",
            "customer_username",
            "status",
            "total",
            "items",
            "created_at",
            "updated_at",
        ]

    def get_total(self, obj: Order) -> str:
        return str(obj.total)


# ── Write serializers ────────────────────────────────────────────────────────

class OrderItemWriteSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_product_id(self, value):
        if not Product.objects.filter(pk=value).exists():
            raise serializers.ValidationError(
                f"Product with id={value} does not exist."
            )
        return value


class OrderCreateSerializer(serializers.Serializer):
    """
    Handles atomic order creation with stock decrement.

    Business rules enforced here:
    - Empty order → 400.
    - Non-positive quantity → 400 (enforced by min_value=1 on child).
    - Unknown product → 400.
    - Insufficient stock for any item → 400; nothing is persisted.
    - Concurrent orders for last unit: SELECT … FOR UPDATE on each product
      row prevents overselling even under race conditions.
    - unit_price is frozen from Product.price at call time.
    """

    items = OrderItemWriteSerializer(many=True)

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("An order must contain at least one item.")

        # Detect duplicate product ids in a single request.
        product_ids = [i["product_id"] for i in items]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "Duplicate products in order. Combine quantities into a single line."
            )
        return items

    def create(self, validated_data):
        customer = self.context["request"].user
        items_data = validated_data["items"]

        with transaction.atomic():
            # Lock product rows in a deterministic order to prevent deadlocks
            # when two concurrent transactions touch overlapping product sets.
            product_ids_sorted = sorted(i["product_id"] for i in items_data)
            products_locked = {
                p.pk: p
                for p in Product.objects.select_for_update().filter(
                    pk__in=product_ids_sorted
                )
            }

            # Validate stock for every item before writing anything.
            stock_errors = {}
            for item in items_data:
                product = products_locked[item["product_id"]]
                if product.stock_quantity < item["quantity"]:
                    stock_errors[product.sku] = (
                        f"Requested {item['quantity']}, "
                        f"only {product.stock_quantity} in stock."
                    )
            if stock_errors:
                raise serializers.ValidationError({"stock": stock_errors})

            # All checks passed — create order and items atomically.
            order = Order.objects.create(customer=customer)

            for item in items_data:
                product = products_locked[item["product_id"]]
                OrderItem.objects.create(
                    order=order,
                    product=product,
                    quantity=item["quantity"],
                    unit_price=product.price,   # price frozen at this instant
                )
                # Decrement stock using F() to avoid race on the cached value.
                Product.objects.filter(pk=product.pk).update(
                    stock_quantity=F("stock_quantity") - item["quantity"]
                )

        return order
