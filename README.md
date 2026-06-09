# Warehouse Order Management API

A production-grade REST API for a warehouse order system built with **Django 5+**, **Django REST Framework**, and **SQLite**. Authentication via **JWT** (SimpleJWT).

---

## Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 5 + DRF 3.15 |
| Auth | djangorestframework-simplejwt |
| Filtering | django-filter |
| Database | SQLite (file-based, zero setup) |

---

## Live Deployment

Deployed on Render: **https://warehouse-api.onrender.com**

> First request may take ~30 seconds (free tier spin-up). All endpoints work as documented below.

---

## Quick Start

```bash
# 1. Clone and enter project
git clone <repo-url>
cd warehouse_api

# 2. Create and activate virtualenv
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run migrations (creates DB + runs data seed + renames column)
python manage.py migrate

# 5. Create a superuser / staff account
python manage.py createsuperuser

# 6. Start the dev server
python manage.py runserver
```

The API is now live at `http://127.0.0.1:8000/api/`.

---

## Running Tests

```bash
python manage.py test products orders --verbosity=2
```

28 tests covering: stock integrity, price freeze, permission isolation, atomic cancellation, race-condition guards, and validation edge cases.

---

## Authentication

All endpoints except `GET /api/products/` require a JWT Bearer token.

```bash
# Obtain tokens
curl -X POST http://127.0.0.1:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "alice", "password": "secret"}'

# Use the access token
curl http://127.0.0.1:8000/api/orders/ \
  -H "Authorization: Bearer <access_token>"

# Refresh
curl -X POST http://127.0.0.1:8000/api/auth/token/refresh/ \
  -d '{"refresh": "<refresh_token>"}'
```

---

## Endpoints

### Auth

| Method | URL | Description |
|--------|-----|-------------|
| POST | `/api/auth/token/` | Obtain JWT pair |
| POST | `/api/auth/token/refresh/` | Refresh access token |
| POST | `/api/auth/token/verify/` | Verify token |

### Products

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| GET | `/api/products/` | None | List products. Anonymous → in-stock only. |
| GET | `/api/products/?in_stock=true` | None | Filter in-stock products. |
| GET | `/api/products/?search=keyboard` | None | Search by name or SKU. |
| POST | `/api/products/` | Staff | Create a product. |
| GET | `/api/products/{id}/` | None | Retrieve a product. |

### Orders

| Method | URL | Auth | Description |
|--------|-----|------|-------------|
| POST | `/api/orders/` | Any user | Place a new order. |
| GET | `/api/orders/` | Any user | List orders (own orders; staff see all). |
| GET | `/api/orders/{id}/` | Any user | Order detail (own; staff see any). |
| POST | `/api/orders/{id}/cancel/` | Any user | Cancel a pending order + restock. |

---

## Example: Place an Order

```bash
curl -X POST http://127.0.0.1:8000/api/orders/ \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"product_id": 1, "quantity": 2},
      {"product_id": 3, "quantity": 1}
    ]
  }'
```

Response:

```json
{
  "id": 7,
  "customer_username": "alice",
  "status": "pending",
  "total": "119.97",
  "items": [
    {
      "id": 13,
      "product_id": 1,
      "product_name": "Mechanical Keyboard TKL",
      "product_sku": "KB-TKL-001",
      "quantity": 2,
      "unit_price": "89.99",
      "line_total": "179.98"
    }
  ],
  "created_at": "2025-07-01T14:22:01Z",
  "updated_at": "2025-07-01T14:22:01Z"
}
```

---

## Migration Story

The migration chain tells a deliberate schema evolution story:

| # | File | What it does |
|---|------|-------------|
| `0001` | `products/0001_initial.py` | Creates `Product` with `quantity_on_hand` field. |
| `0002` | `products/0002_seed_products.py` | `RunPython` — inserts 5 real products into `quantity_on_hand`. |
| `0003` | `products/0003_rename_quantity_on_hand_stock_quantity.py` | `RenameField` — renames column to `stock_quantity`. **No data loss.** |

Running `python manage.py migrate` on a blank database will execute all three steps in order. The seeded products created in step 2 will have their original stock values intact after the rename in step 3 — verified by the migration test above.

---

## Key Design Decisions & Tradeoffs

### Stock Integrity (Race Conditions)
`OrderCreateSerializer.create()` wraps the entire operation in `transaction.atomic()` and uses `SELECT FOR UPDATE` on product rows, sorted by primary key to prevent deadlocks. Stock is decremented via `F()` expressions to avoid lost-update bugs from cached Python values.

### Price Freeze
`OrderItem.unit_price` is written once at order creation from `Product.price` at that instant. It is never updated. Changing a product's price post-order has zero effect on historical totals.

### Permission Model
- **Anonymous**: `GET /api/products/` only, filtered to in-stock.
- **Authenticated customers**: place orders, view/cancel own orders only.
- **Staff**: full product CRUD, see all orders, cancel any order.
- Cross-user order access returns **404** (not 403) — the queryset is scoped per owner, so other users' order IDs are simply not found. This avoids leaking the existence of orders.

### Cancel Atomicity
The cancel endpoint re-fetches the order with `SELECT FOR UPDATE` inside the transaction to guard against two concurrent cancel requests racing on the same order. A second concurrent cancel sees status != PENDING and gets a 409 Conflict.

### SQLite Concurrency Limit
`SELECT FOR UPDATE` on SQLite is supported by Django via its table-level write lock. In high-concurrency production use, migrating to PostgreSQL would give row-level locking and better throughput. This is a known SQLite tradeoff, acceptable per the project spec.

---

## Seeded Products (Available After `migrate`)

| Name | SKU | Price | Stock |
|------|-----|-------|-------|
| Mechanical Keyboard TKL | KB-TKL-001 | $89.99 | 150 |
| Wireless Ergonomic Mouse | MS-WRL-002 | $49.99 | 320 |
| 27-inch 4K Monitor | MN-4K-003 | $399.00 | 45 |
| USB-C Docking Station | DK-USC-004 | $129.50 | 80 |
| Noise-Cancelling Headset | HS-NC-005 | $199.00 | 0 (out of stock) |

