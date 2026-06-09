from rest_framework import serializers
from .models import Product


class ProductSerializer(serializers.ModelSerializer):
    in_stock = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "sku",
            "price",
            "stock_quantity",
            "in_stock",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_in_stock(self, obj: Product) -> bool:
        return obj.stock_quantity > 0

    def validate_price(self, value):
        if value <= 0:
            raise serializers.ValidationError("Price must be greater than zero.")
        return value
