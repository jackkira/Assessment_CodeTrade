"""
Builds store.db — a small retail database for the agent take-home.
Deterministic (fixed seed) so every candidate gets identical data.
"""
import sqlite3, random, datetime as dt, os

random.seed(42)
DB = "store.db"
if os.path.exists(DB):
    os.remove(DB)

con = sqlite3.connect(DB)
c = con.cursor()

c.executescript("""
CREATE TABLE customers (
    customer_id   INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    city          TEXT NOT NULL,
    signup_date   TEXT NOT NULL,        -- ISO date
    segment       TEXT NOT NULL         -- 'consumer' | 'business'
);

CREATE TABLE products (
    product_id    INTEGER PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    unit_price    REAL NOT NULL,
    active        INTEGER NOT NULL      -- 1 active, 0 discontinued
);

CREATE TABLE orders (
    order_id      INTEGER PRIMARY KEY,
    customer_id   INTEGER NOT NULL,
    order_date    TEXT NOT NULL,        -- ISO date
    status        TEXT NOT NULL,        -- 'completed' | 'returned' | 'cancelled'
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    order_item_id INTEGER PRIMARY KEY,
    order_id      INTEGER NOT NULL,
    product_id    INTEGER NOT NULL,
    quantity      INTEGER NOT NULL,
    unit_price    REAL NOT NULL,        -- price at time of sale
    FOREIGN KEY (order_id)  REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
""")

cities = ["Mumbai", "Pune", "Ahmedabad", "Bengaluru", "Delhi", "Chennai", "Hyderabad"]
first = ["Aarav","Diya","Vivaan","Anaya","Kabir","Mira","Arjun","Saanvi","Reyansh","Isha",
         "Dev","Tara","Kian","Nisha","Rohan","Priya","Aman","Sara","Yash","Lila"]
last  = ["Shah","Patel","Mehta","Rao","Iyer","Nair","Gupta","Singh","Joshi","Desai"]

# ---- customers ----
customers = []
base = dt.date(2023, 1, 1)
for cid in range(1, 41):
    name = f"{random.choice(first)} {random.choice(last)}"
    city = random.choice(cities)
    signup = base + dt.timedelta(days=random.randint(0, 540))
    segment = random.choice(["consumer", "consumer", "business"])
    customers.append((cid, name, city, signup.isoformat(), segment))
c.executemany("INSERT INTO customers VALUES (?,?,?,?,?)", customers)

# ---- products ----
catalog = [
    ("Aurora Desk Lamp","Lighting",2200,1),
    ("Nimbus Office Chair","Furniture",8900,1),
    ("Cobalt Standing Desk","Furniture",18500,1),
    ("Pulse Wireless Mouse","Electronics",1200,1),
    ("Pulse Mechanical Keyboard","Electronics",4500,1),
    ("Vertex Monitor 27","Electronics",16500,1),
    ("Slate Notebook A5","Stationery",250,1),
    ("Slate Gel Pen 5-pack","Stationery",180,1),
    ("Echo Bluetooth Speaker","Electronics",3200,0),   # discontinued
    ("Halo LED Strip","Lighting",1500,1),
    ("Terra Desk Plant","Decor",650,1),
    ("Terra Ceramic Mug","Decor",420,1),
    ("Cobalt Cable Tray","Furniture",900,1),
    ("Vertex Laptop Stand","Electronics",2100,1),
    ("Aurora Floor Lamp","Lighting",5400,0),           # discontinued
]
products = [(pid+1, n, cat, price, act) for pid,(n,cat,price,act) in enumerate(catalog)]
c.executemany("INSERT INTO products VALUES (?,?,?,?,?)", products)

# ---- orders + order_items ----
order_id = 0
item_id = 0
orders, items = [], []
start = dt.date(2025, 1, 1)
end   = dt.date(2025, 6, 30)
span  = (end - start).days

for cid, *_ in customers:
    n_orders = random.choices([0,1,2,3,4,5,6], weights=[1,3,4,4,3,2,1])[0]
    for _ in range(n_orders):
        order_id += 1
        odate = start + dt.timedelta(days=random.randint(0, span))
        status = random.choices(["completed","returned","cancelled"], weights=[8,1,1])[0]
        orders.append((order_id, cid, odate.isoformat(), status))
        for _ in range(random.randint(1,4)):
            item_id += 1
            pid, pname, cat, price, act = random.choice(products)
            qty = random.randint(1,3)
            # small price drift vs catalog
            sale_price = round(price * random.uniform(0.95, 1.05), 2)
            items.append((item_id, order_id, pid, qty, sale_price))

c.executemany("INSERT INTO orders VALUES (?,?,?,?)", orders)
c.executemany("INSERT INTO order_items VALUES (?,?,?,?,?)", items)

con.commit()

# ---- quick sanity summary ----
def q(sql):
    return c.execute(sql).fetchone()[0]

print("customers   :", q("SELECT COUNT(*) FROM customers"))
print("products    :", q("SELECT COUNT(*) FROM products"))
print("orders      :", q("SELECT COUNT(*) FROM orders"))
print("order_items :", q("SELECT COUNT(*) FROM order_items"))
print("completed   :", q("SELECT COUNT(*) FROM orders WHERE status='completed'"))
print("returned    :", q("SELECT COUNT(*) FROM orders WHERE status='returned'"))
con.close()
print("\nWrote", DB)
