from rest_framework import viewsets, filters
from django_filters.rest_framework import DjangoFilterBackend

from .models import Product
from .serializers import ProductSerializer
from .filters import ProductFilter
from .permissions import IsStaffOrReadOnlyForAuthenticated


class ProductViewSet(viewsets.ModelViewSet):
    """
    GET  /api/products/       — list products
    POST /api/products/       — create product (staff only)
    GET  /api/products/{id}/  — retrieve product

    Anonymous users see only in-stock products by default.
    Authenticated users and staff can see all products (and filter freely).
    Staff can create / update / delete products.
    """

    serializer_class = ProductSerializer
    permission_classes = [IsStaffOrReadOnlyForAuthenticated]
    filterset_class = ProductFilter
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["name", "sku"]
    http_method_names = ["get", "post", "put", "patch", "delete", "head", "options"]

    def get_queryset(self):
        qs = Product.objects.all()
        # Anonymous users see only in-stock products by default.
        if not (self.request.user and self.request.user.is_authenticated):
            qs = qs.filter(stock_quantity__gt=0)
        return qs
