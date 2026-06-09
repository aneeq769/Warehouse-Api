"""
Migration 0002 — Data seed (RunPython).

Inserts real product rows so that actual values live in the
`quantity_on_hand` column before the rename happens in 0003.
Running migrate on a fresh DB will produce these rows and they must
survive the rename with their stock values intact.
"""

from django.db import migrations


SEED_PRODUCTS = [
    {
        "name": "Mechanical Keyboard TKL",
        "sku": "KB-TKL-001",
        "price": "89.99",
        "quantity_on_hand": 150,
    },
    {
        "name": "Wireless Ergonomic Mouse",
        "sku": "MS-WRL-002",
        "price": "49.99",
        "quantity_on_hand": 320,
    },
    {
        "name": "27-inch 4K Monitor",
        "sku": "MN-4K-003",
        "price": "399.00",
        "quantity_on_hand": 45,
    },
    {
        "name": "USB-C Docking Station",
        "sku": "DK-USC-004",
        "price": "129.50",
        "quantity_on_hand": 80,
    },
    {
        "name": "Noise-Cancelling Headset",
        "sku": "HS-NC-005",
        "price": "199.00",
        "quantity_on_hand": 0,   # intentionally out-of-stock seed
    },
]


def seed_products(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    for data in SEED_PRODUCTS:
        Product.objects.get_or_create(sku=data["sku"], defaults=data)


def unseed_products(apps, schema_editor):
    Product = apps.get_model("products", "Product")
    skus = [p["sku"] for p in SEED_PRODUCTS]
    Product.objects.filter(sku__in=skus).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_products, reverse_code=unseed_products),
    ]
