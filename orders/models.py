from django.conf import settings
from django.db import models


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        SHIPPED = "shipped", "Shipped"
        CANCELLED = "cancelled", "Cancelled"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Order #{self.pk} — {self.customer} [{self.status}]"

    @property
    def total(self) -> "Decimal":
        """Computed from frozen unit_price values — never changes post-creation."""
        from decimal import Decimal

        return sum(
            item.unit_price * item.quantity for item in self.items.all()
        ) or Decimal("0.00")


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    quantity = models.PositiveIntegerField()
    # Price frozen at order-creation time. Product price changes must NOT
    # affect this value.
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = [("order", "product")]

    def __str__(self) -> str:
        return f"{self.quantity}× {self.product.sku} @ {self.unit_price}"
