from django.db import models


class Product(models.Model):
    """
    Represents a warehouse product.

    Migration history note:
      - Migration 0001: created with `quantity_on_hand` field.
      - Migration 0002: data seed (RunPython) — inserts real products.
      - Migration 0003: renamed `quantity_on_hand` → `stock_quantity` (RenameField,
        no data loss).  All application code references `stock_quantity`.
    """

    name = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    # Final name after migration 0003 rename.
    stock_quantity = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.sku})"
