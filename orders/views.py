from django.db import transaction
from django.db.models import F
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Order, OrderItem
from .serializers import OrderCreateSerializer, OrderReadSerializer
from .permissions import IsOwnerOrStaff


class OrderViewSet(viewsets.GenericViewSet):
    """
    POST /api/orders/           — place a new order (authenticated users)
    GET  /api/orders/           — list orders (own for customers, all for staff)
    GET  /api/orders/{id}/      — order detail (own for customers, any for staff)
    POST /api/orders/{id}/cancel/ — cancel a pending order and restock items
    """

    permission_classes = [IsOwnerOrStaff]

    def get_queryset(self):
        qs = Order.objects.prefetch_related("items__product")
        if self.request.user.is_staff:
            return qs
        return qs.filter(customer=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderReadSerializer

    # ── POST /api/orders/ ────────────────────────────────────────────────────
    def create(self, request):
        serializer = OrderCreateSerializer(
            data=request.data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(
            OrderReadSerializer(order, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    # ── GET /api/orders/ ─────────────────────────────────────────────────────
    def list(self, request):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = OrderReadSerializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = OrderReadSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)

    # ── GET /api/orders/{id}/ ────────────────────────────────────────────────
    def retrieve(self, request, pk=None):
        order = self.get_object()
        serializer = OrderReadSerializer(order, context={"request": request})
        return Response(serializer.data)

    # ── POST /api/orders/{id}/cancel/ ────────────────────────────────────────
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        order = self.get_object()  # triggers IsOwnerOrStaff.has_object_permission

        if order.status == Order.Status.SHIPPED:
            return Response(
                {"detail": "Shipped orders cannot be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.status == Order.Status.CANCELLED:
            return Response(
                {"detail": "This order is already cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.status != Order.Status.PENDING:
            return Response(
                {
                    "detail": (
                        f"Only pending orders can be cancelled. "
                        f"Current status: {order.status}."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Re-fetch with lock to avoid concurrent cancel races.
            order = Order.objects.select_for_update().get(pk=order.pk)

            # Guard against a concurrent cancel that already finished.
            if order.status != Order.Status.PENDING:
                return Response(
                    {"detail": "Order status changed concurrently. Refresh and retry."},
                    status=status.HTTP_409_CONFLICT,
                )

            # Restock each item atomically.
            for item in order.items.select_related("product"):
                from products.models import Product
                Product.objects.filter(pk=item.product_id).update(
                    stock_quantity=F("stock_quantity") + item.quantity
                )

            order.status = Order.Status.CANCELLED
            order.save(update_fields=["status", "updated_at"])

        order.refresh_from_db()
        return Response(
            OrderReadSerializer(order, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
