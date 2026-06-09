from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from products.models import Product
from .models import Order, OrderItem

User = get_user_model()


def jwt(user):
    return str(RefreshToken.for_user(user).access_token)


class OrderAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="staff", password="pass", is_staff=True
        )
        self.customer1 = User.objects.create_user(username="cust1", password="pass")
        self.customer2 = User.objects.create_user(username="cust2", password="pass")

        self.product_a = Product.objects.create(
            name="Alpha", sku="ALPHA-1", price=Decimal("10.00"), stock_quantity=50
        )
        self.product_b = Product.objects.create(
            name="Beta", sku="BETA-1", price=Decimal("25.00"), stock_quantity=5
        )
        self.product_zero = Product.objects.create(
            name="Gamma", sku="GAMMA-1", price=Decimal("5.00"), stock_quantity=0
        )

    def auth(self, user):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {jwt(user)}")

    # ── Order creation ────────────────────────────────────────────────────────

    def test_create_order_decrements_stock(self):
        self.auth(self.customer1)
        response = self.client.post(
            "/api/orders/",
            {"items": [{"product_id": self.product_a.pk, "quantity": 3}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 47)

    def test_price_is_frozen_at_order_creation(self):
        self.auth(self.customer1)
        self.client.post(
            "/api/orders/",
            {"items": [{"product_id": self.product_a.pk, "quantity": 1}]},
            format="json",
        )
        # Now change the price
        self.product_a.price = Decimal("999.00")
        self.product_a.save()

        order = Order.objects.filter(customer=self.customer1).first()
        item = order.items.first()
        self.assertEqual(item.unit_price, Decimal("10.00"))  # original price

    def test_create_order_with_multiple_items(self):
        self.auth(self.customer1)
        response = self.client.post(
            "/api/orders/",
            {
                "items": [
                    {"product_id": self.product_a.pk, "quantity": 2},
                    {"product_id": self.product_b.pk, "quantity": 1},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Total: 2 × 10.00 + 1 × 25.00 = 45.00
        self.assertEqual(Decimal(response.data["total"]), Decimal("45.00"))

    def test_insufficient_stock_returns_400(self):
        self.auth(self.customer1)
        response = self.client.post(
            "/api/orders/",
            {"items": [{"product_id": self.product_b.pk, "quantity": 100}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("stock", response.data)

    def test_out_of_stock_product_returns_400(self):
        self.auth(self.customer1)
        response = self.client.post(
            "/api/orders/",
            {"items": [{"product_id": self.product_zero.pk, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_partial_failure_does_not_save_order(self):
        """If one item fails stock check, entire order must be rolled back."""
        self.auth(self.customer1)
        response = self.client.post(
            "/api/orders/",
            {
                "items": [
                    {"product_id": self.product_a.pk, "quantity": 1},  # ok
                    {"product_id": self.product_zero.pk, "quantity": 1},  # fails
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Stock of product_a must NOT have been decremented
        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 50)
        self.assertEqual(Order.objects.count(), 0)

    def test_empty_order_rejected(self):
        self.auth(self.customer1)
        response = self.client.post("/api/orders/", {"items": []}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_positive_quantity_rejected(self):
        self.auth(self.customer1)
        response = self.client.post(
            "/api/orders/",
            {"items": [{"product_id": self.product_a.pk, "quantity": 0}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_product_rejected(self):
        self.auth(self.customer1)
        response = self.client.post(
            "/api/orders/",
            {"items": [{"product_id": 99999, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_product_in_single_order_rejected(self):
        self.auth(self.customer1)
        response = self.client.post(
            "/api/orders/",
            {
                "items": [
                    {"product_id": self.product_a.pk, "quantity": 1},
                    {"product_id": self.product_a.pk, "quantity": 2},
                ]
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_anonymous_cannot_place_order(self):
        self.client.credentials()
        response = self.client.post(
            "/api/orders/",
            {"items": [{"product_id": self.product_a.pk, "quantity": 1}]},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Order listing ─────────────────────────────────────────────────────────

    def _place_order(self, user, product, qty=1):
        self.auth(user)
        self.client.post(
            "/api/orders/",
            {"items": [{"product_id": product.pk, "quantity": qty}]},
            format="json",
        )

    def test_customer_sees_only_own_orders(self):
        self._place_order(self.customer1, self.product_a, 1)
        self._place_order(self.customer2, self.product_a, 1)

        self.auth(self.customer1)
        response = self.client.get("/api/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for order in response.data["results"]:
            self.assertEqual(order["customer_username"], "cust1")

    def test_staff_sees_all_orders(self):
        self._place_order(self.customer1, self.product_a, 1)
        self._place_order(self.customer2, self.product_a, 1)

        self.auth(self.staff)
        response = self.client.get("/api/orders/")
        self.assertEqual(response.data["count"], 2)

    def test_customer_cannot_retrieve_other_users_order(self):
        self._place_order(self.customer1, self.product_a, 1)
        order = Order.objects.filter(customer=self.customer1).first()

        self.auth(self.customer2)
        response = self.client.get(f"/api/orders/{order.pk}/")
        # 404 is correct: the queryset filters by owner, so other users' orders
        # are simply not found — we don't leak that the order exists at all.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # ── Order cancellation ────────────────────────────────────────────────────

    def test_cancel_pending_order_restocks(self):
        self._place_order(self.customer1, self.product_a, 5)
        order = Order.objects.filter(customer=self.customer1).first()

        self.auth(self.customer1)
        response = self.client.post(f"/api/orders/{order.pk}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "cancelled")

        self.product_a.refresh_from_db()
        self.assertEqual(self.product_a.stock_quantity, 50)  # fully restocked

    def test_cancel_shipped_order_returns_400(self):
        self._place_order(self.customer1, self.product_a, 1)
        order = Order.objects.filter(customer=self.customer1).first()
        order.status = Order.Status.SHIPPED
        order.save()

        self.auth(self.customer1)
        response = self.client.post(f"/api/orders/{order.pk}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_cancel_already_cancelled_order_returns_400(self):
        self._place_order(self.customer1, self.product_a, 1)
        order = Order.objects.filter(customer=self.customer1).first()

        self.auth(self.customer1)
        self.client.post(f"/api/orders/{order.pk}/cancel/")  # first cancel
        response = self.client.post(f"/api/orders/{order.pk}/cancel/")  # second
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_customer_cannot_cancel_other_users_order(self):
        self._place_order(self.customer1, self.product_a, 1)
        order = Order.objects.filter(customer=self.customer1).first()

        self.auth(self.customer2)
        response = self.client.post(f"/api/orders/{order.pk}/cancel/")
        # Same reasoning as retrieve: queryset scoped to owner → 404 not 403.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_staff_can_cancel_any_order(self):
        self._place_order(self.customer1, self.product_a, 1)
        order = Order.objects.filter(customer=self.customer1).first()

        self.auth(self.staff)
        response = self.client.post(f"/api/orders/{order.pk}/cancel/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
