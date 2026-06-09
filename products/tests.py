from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Product

User = get_user_model()


def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return str(refresh.access_token)


class ProductAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.customer = User.objects.create_user(
            username="customer", password="pass"
        )
        self.product_in_stock = Product.objects.create(
            name="Widget A", sku="WGT-A", price=Decimal("9.99"), stock_quantity=100
        )
        self.product_out_of_stock = Product.objects.create(
            name="Widget B", sku="WGT-B", price=Decimal("4.99"), stock_quantity=0
        )

    def auth(self, user):
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {get_tokens_for_user(user)}"
        )

    # ── Anonymous access ─────────────────────────────────────────────────────

    def test_anonymous_can_list_products(self):
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_only_sees_in_stock_products(self):
        response = self.client.get("/api/products/")
        skus = [p["sku"] for p in response.data["results"]]
        self.assertIn("WGT-A", skus)
        self.assertNotIn("WGT-B", skus)

    def test_anonymous_cannot_create_product(self):
        response = self.client.post(
            "/api/products/", {"name": "X", "sku": "X-01", "price": "1.00", "stock_quantity": 5}
        )
        # JWTAuthentication returns 401 for unauthenticated requests before
        # permission classes even run — correct behaviour.
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    # ── Staff access ─────────────────────────────────────────────────────────

    def test_staff_can_create_product(self):
        self.auth(self.staff)
        response = self.client.post(
            "/api/products/",
            {"name": "New Product", "sku": "NEW-01", "price": "19.99", "stock_quantity": 50},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["sku"], "NEW-01")

    def test_staff_sees_all_products(self):
        self.auth(self.staff)
        response = self.client.get("/api/products/")
        skus = [p["sku"] for p in response.data["results"]]
        self.assertIn("WGT-A", skus)
        self.assertIn("WGT-B", skus)

    # ── Non-staff cannot create ───────────────────────────────────────────────

    def test_customer_cannot_create_product(self):
        self.auth(self.customer)
        response = self.client.post(
            "/api/products/",
            {"name": "X", "sku": "X-02", "price": "5.00", "stock_quantity": 10},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── Filtering ─────────────────────────────────────────────────────────────

    def test_in_stock_filter(self):
        self.auth(self.staff)
        response = self.client.get("/api/products/?in_stock=true")
        skus = [p["sku"] for p in response.data["results"]]
        self.assertIn("WGT-A", skus)
        self.assertNotIn("WGT-B", skus)

    def test_search_by_name(self):
        self.auth(self.staff)
        response = self.client.get("/api/products/?search=Widget A")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["sku"], "WGT-A")

    def test_search_by_sku(self):
        self.auth(self.staff)
        response = self.client.get("/api/products/?search=WGT-B")
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["sku"], "WGT-B")
