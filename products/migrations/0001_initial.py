"""
Migration 0001 — Initial schema.

Product is created with the original field name `quantity_on_hand`.
This represents the first commit of the schema before the business
decided to rename the column.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Product",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("sku", models.CharField(max_length=100, unique=True)),
                ("price", models.DecimalField(decimal_places=2, max_digits=10)),
                # Original column name — will be renamed in migration 0003.
                ("quantity_on_hand", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["name"],
            },
        ),
    ]
