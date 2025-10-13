import os
import sqlite3
import random
from datetime import datetime, timedelta
from pathlib import Path

DB_NAME = os.getenv("SCQB_NEW_DB_NAME", "supply_chain_new.db")

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
  category_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS products (
  product_id INTEGER PRIMARY KEY,
  sku TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  category_id INTEGER NOT NULL,
  unit_cost REAL NOT NULL,
  unit_price REAL NOT NULL,
  reorder_point INTEGER NOT NULL DEFAULT 10,
  reorder_qty INTEGER NOT NULL DEFAULT 50,
  FOREIGN KEY (category_id) REFERENCES categories(category_id)
);

CREATE TABLE IF NOT EXISTS suppliers (
  supplier_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  contact_email TEXT,
  lead_time_days INTEGER NOT NULL DEFAULT 7
);

CREATE TABLE IF NOT EXISTS warehouses (
  warehouse_id INTEGER PRIMARY KEY,
  code TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  city TEXT NOT NULL,
  region TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS customers (
  customer_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT NOT NULL,
  region TEXT NOT NULL,
  segment TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS inventory (
  warehouse_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  on_hand INTEGER NOT NULL DEFAULT 0,
  allocated INTEGER NOT NULL DEFAULT 0,
  safety_stock INTEGER NOT NULL DEFAULT 5,
  PRIMARY KEY (warehouse_id, product_id),
  FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS carriers (
  carrier_id INTEGER PRIMARY KEY,
  name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS purchase_orders (
  po_id INTEGER PRIMARY KEY,
  supplier_id INTEGER NOT NULL,
  order_date TEXT NOT NULL,
  expected_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('OPEN','PARTIAL','CLOSED','CANCELLED')),
  FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id)
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
  po_item_id INTEGER PRIMARY KEY,
  po_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  qty_ordered INTEGER NOT NULL,
  unit_cost REAL NOT NULL,
  qty_received INTEGER NOT NULL DEFAULT 0,
  FOREIGN KEY (po_id) REFERENCES purchase_orders(po_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS sales_orders (
  so_id INTEGER PRIMARY KEY,
  customer_id INTEGER NOT NULL,
  order_date TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('OPEN','ALLOCATED','SHIPPED','CANCELLED')),
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS sales_order_items (
  so_item_id INTEGER PRIMARY KEY,
  so_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  qty INTEGER NOT NULL,
  unit_price REAL NOT NULL,
  FOREIGN KEY (so_id) REFERENCES sales_orders(so_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS shipments (
  shipment_id INTEGER PRIMARY KEY,
  so_id INTEGER NOT NULL,
  warehouse_id INTEGER NOT NULL,
  ship_date TEXT NOT NULL,
  delivered_date TEXT,
  carrier_id INTEGER,
  on_time INTEGER NOT NULL CHECK (on_time IN (0,1)),
  FOREIGN KEY (so_id) REFERENCES sales_orders(so_id),
  FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id),
  FOREIGN KEY (carrier_id) REFERENCES carriers(carrier_id)
);

CREATE TABLE IF NOT EXISTS shipment_items (
  shipment_item_id INTEGER PRIMARY KEY,
  shipment_id INTEGER NOT NULL,
  product_id INTEGER NOT NULL,
  qty INTEGER NOT NULL,
  FOREIGN KEY (shipment_id) REFERENCES shipments(shipment_id),
  FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- Useful views for KPIs
CREATE VIEW IF NOT EXISTS v_inventory_turnover AS
SELECT p.product_id, p.name,
       SUM(CASE WHEN soi.qty IS NOT NULL THEN soi.qty ELSE 0 END) AS units_sold,
       AVG(NULLIF(i.on_hand,0)) AS avg_inventory
FROM products p
LEFT JOIN sales_order_items soi ON soi.product_id = p.product_id
LEFT JOIN inventory i ON i.product_id = p.product_id
GROUP BY p.product_id, p.name;

CREATE VIEW IF NOT EXISTS v_on_time_delivery AS
SELECT strftime('%Y-%m', ship_date) AS month,
       COUNT(*) AS total_shipments,
       SUM(on_time) AS on_time_shipments,
       ROUND(100.0 * SUM(on_time) / NULLIF(COUNT(*),0), 2) AS on_time_pct
FROM shipments
GROUP BY strftime('%Y-%m', ship_date)
ORDER BY month;
"""

CATEGORIES = [
    "Electronics",
    "Home Appliances",
    "Furniture",
    "Grocery",
]

REGIONS = ["North", "South", "East", "West"]
CITIES = [
    "Chennai", "Mumbai", "Delhi", "Bengaluru",
    "Hyderabad", "Pune", "Kolkata", "Ahmedabad"
]
SEGMENTS = ["Retail", "Wholesale", "Online"]
CARRIERS = ["BlueDart", "DTDC", "Delhivery", "EcomExpress"]

random.seed(42)


def daterange(start_days_ago: int, end_days_ago: int) -> datetime:
    days_ago = random.randint(end_days_ago, start_days_ago)
    return datetime.now() - timedelta(days=days_ago)


def main():
    db_path = Path(DB_NAME)
    if db_path.exists():
        print(f"Removing existing DB: {db_path}")
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON;")
    cur = conn.cursor()

    print("Creating schema...")
    cur.executescript(SCHEMA_SQL)

    print("Seeding reference data...")
    # Categories
    for name in CATEGORIES:
        cur.execute("INSERT INTO categories(name) VALUES (?)", (name,))

    # Products (20)
    products = []
    for i in range(1, 21):
        category_id = random.randint(1, len(CATEGORIES))
        sku = f"SKU-{1000 + i}"
        name = f"Product {i:02d}"
        unit_cost = round(random.uniform(5, 200), 2)
        unit_price = round(unit_cost * random.uniform(1.2, 1.8), 2)
        reorder_point = random.randint(5, 30)
        reorder_qty = random.randint(20, 100)
        cur.execute(
            """
            INSERT INTO products(sku, name, category_id, unit_cost, unit_price, reorder_point, reorder_qty)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (sku, name, category_id, unit_cost, unit_price, reorder_point, reorder_qty),
        )
        products.append(cur.lastrowid)

    # Suppliers (5)
    for i in range(1, 6):
        cur.execute(
            "INSERT INTO suppliers(name, contact_email, lead_time_days) VALUES (?, ?, ?)",
            (f"Supplier {i}", f"supplier{i}@example.com", random.randint(3, 14)),
        )

    # Warehouses (3)
    for i, city in enumerate(random.sample(CITIES, 3), start=1):
        cur.execute(
            "INSERT INTO warehouses(code, name, city, region) VALUES (?, ?, ?, ?)",
            (f"W{i:02d}", f"Warehouse {i}", city, random.choice(REGIONS)),
        )

    # Customers (30)
    for i in range(1, 31):
        cur.execute(
            "INSERT INTO customers(name, city, region, segment) VALUES (?, ?, ?, ?)",
            (f"Customer {i:03d}", random.choice(CITIES), random.choice(REGIONS), random.choice(SEGMENTS)),
        )

    # Carriers
    for name in CARRIERS:
        cur.execute("INSERT INTO carriers(name) VALUES (?)", (name,))

    # Inventory: all products x all warehouses
    cur.execute("SELECT warehouse_id FROM warehouses")
    warehouses = [row[0] for row in cur.fetchall()]
    for wid in warehouses:
        for pid in products:
            on_hand = random.randint(0, 500)
            allocated = random.randint(0, min(on_hand, 100))
            safety = random.randint(5, 30)
            cur.execute(
                "INSERT INTO inventory(warehouse_id, product_id, on_hand, allocated, safety_stock) VALUES (?, ?, ?, ?, ?)",
                (wid, pid, on_hand, allocated, safety),
            )

    # Purchase Orders (30) and items
    for _ in range(30):
        supplier_id = random.randint(1, 5)
        order_date = daterange(120, 30)
        expected_date = order_date + timedelta(days=random.randint(3, 14))
        status = random.choice(["OPEN", "PARTIAL", "CLOSED"])
        cur.execute(
            "INSERT INTO purchase_orders(supplier_id, order_date, expected_date, status) VALUES (?, ?, ?, ?)",
            (supplier_id, order_date.strftime("%Y-%m-%d"), expected_date.strftime("%Y-%m-%d"), status),
        )
        po_id = cur.lastrowid
        for _ in range(random.randint(2, 5)):
            pid = random.choice(products)
            qty = random.randint(10, 200)
            unit_cost = cur.execute("SELECT unit_cost FROM products WHERE product_id=?", (pid,)).fetchone()[0]
            qty_received = qty if status == "CLOSED" else random.randint(0, qty)
            cur.execute(
                """
                INSERT INTO purchase_order_items(po_id, product_id, qty_ordered, unit_cost, qty_received)
                VALUES (?, ?, ?, ?, ?)
                """,
                (po_id, pid, qty, unit_cost, qty_received),
            )

    # Sales Orders (100) and items
    for _ in range(100):
        customer_id = random.randint(1, 30)
        order_date = daterange(90, 0)
        status = random.choice(["OPEN", "ALLOCATED", "SHIPPED"])
        cur.execute(
            "INSERT INTO sales_orders(customer_id, order_date, status) VALUES (?, ?, ?)",
            (customer_id, order_date.strftime("%Y-%m-%d"), status),
        )
        so_id = cur.lastrowid
        for _ in range(random.randint(1, 4)):
            pid = random.choice(products)
            qty = random.randint(1, 20)
            unit_price = cur.execute("SELECT unit_price FROM products WHERE product_id=?", (pid,)).fetchone()[0]
            cur.execute(
                "INSERT INTO sales_order_items(so_id, product_id, qty, unit_price) VALUES (?, ?, ?, ?)",
                (so_id, pid, qty, unit_price),
            )

    # Shipments for shipped orders
    so_rows = cur.execute("SELECT so_id, order_date FROM sales_orders WHERE status='SHIPPED'").fetchall()
    for (so_id, order_date_str) in so_rows:
        order_date = datetime.strptime(order_date_str, "%Y-%m-%d")
        ship_date = order_date + timedelta(days=random.randint(0, 5))
        delivered_date = ship_date + timedelta(days=random.randint(1, 7))
        warehouse_id = random.choice(warehouses)
        carrier_id = random.randint(1, len(CARRIERS))
        on_time = 1 if (delivered_date - ship_date).days <= 5 else 0
        cur.execute(
            """
            INSERT INTO shipments(so_id, warehouse_id, ship_date, delivered_date, carrier_id, on_time)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                so_id,
                warehouse_id,
                ship_date.strftime("%Y-%m-%d"),
                delivered_date.strftime("%Y-%m-%d"),
                carrier_id,
                on_time,
            ),
        )
        shipment_id = cur.lastrowid
        # fill shipment items to match order roughly
        items = cur.execute("SELECT product_id, qty FROM sales_order_items WHERE so_id=?", (so_id,)).fetchall()
        for (pid, qty) in items:
            cur.execute(
                "INSERT INTO shipment_items(shipment_id, product_id, qty) VALUES (?, ?, ?)",
                (shipment_id, pid, qty),
            )

    conn.commit()
    conn.close()
    print(f"Created DB at {db_path.resolve()}")


if __name__ == "__main__":
    main()
