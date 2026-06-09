"""
Migration 0003 — Rename column.

Renames `quantity_on_hand` → `stock_quantity` using Django's RenameField,
which translates to a single ALTER TABLE … RENAME COLUMN statement on
databases that support it (SQLite included via Django's rewrite mechanism).

This does NOT drop and recreate the column, so all data seeded in
migration 0002 is preserved with its original values.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0002_seed_products"),
    ]

    operations = [
        migrations.RenameField(
            model_name="product",
            old_name="quantity_on_hand",
            new_name="stock_quantity",
        ),
    ]
