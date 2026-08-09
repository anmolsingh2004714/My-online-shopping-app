"""SQLite access helpers for the ShopKart demo store."""

import os
import sqlite3

from flask import current_app, g
from werkzeug.security import generate_password_hash

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    phone TEXT,
    password TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    price REAL NOT NULL,
    stock INTEGER NOT NULL DEFAULT 0,
    category TEXT NOT NULL,
    image TEXT NOT NULL DEFAULT '',
    rating REAL NOT NULL DEFAULT 4.5
);

CREATE TABLE IF NOT EXISTS cart_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1,
    UNIQUE(user_id, product_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    total REAL NOT NULL,
    address TEXT NOT NULL,
    placed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INTEGER NOT NULL REFERENCES products(id),
    name TEXT NOT NULL,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL
);
"""

DEMO_PRODUCTS = [
    (
        "Aurora Wireless Headphones",
        "Over-ear ANC headphones with 40 hour battery life and USB-C fast charge.",
        4999.0,
        18,
        "Audio",
        "headphones.webp",
        4.7,
    ),
    (
        "Pulse Gaming Mouse",
        "16000 DPI optical sensor, six programmable buttons and braided cable.",
        1499.0,
        42,
        "Accessories",
        "mouse.webp",
        4.5,
    ),
    (
        "Nimbus Smart Watch",
        "AMOLED display, SpO2 and heart-rate tracking with 7 day battery.",
        3299.0,
        25,
        "Wearables",
        "watch.webp",
        4.4,
    ),
    (
        "Kraft Mechanical Keyboard",
        "Hot-swappable 75% layout with tactile brown switches and RGB backlight.",
        5499.0,
        11,
        "Accessories",
        "keyboard.webp",
        4.8,
    ),
    (
        "Volt 20K Power Bank",
        "20000 mAh with 45W power delivery and dual USB-C output.",
        2199.0,
        60,
        "Power",
        "powerbank.webp",
        4.3,
    ),
    (
        "Studio Ring Light",
        "12 inch bi-colour LED ring light with tripod and phone mount.",
        1899.0,
        30,
        "Studio",
        "ringlight.webp",
        4.2,
    ),
    (
        "Echo Bluetooth Speaker",
        "IPX7 waterproof speaker with 360 degree sound and 24 hour playback.",
        2799.0,
        22,
        "Audio",
        "speaker.webp",
        4.6,
    ),
    (
        "Trek Laptop Backpack",
        "Water resistant 25L backpack with padded 16 inch laptop sleeve.",
        2499.0,
        35,
        "Bags",
        "backpack.webp",
        4.5,
    ),
]

DEMO_USER = ("Demo Shopper", "demo@shopkart.test", "9876543210", "demo1234")


def get_db():
    """Return the request-scoped SQLite connection."""

    if "db" not in g:
        g.db = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


def close_db(exception=None):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def init_db(app):
    """Create the schema and seed demo data when the store is empty."""

    directory = os.path.dirname(app.config["DATABASE"])
    if directory:
        os.makedirs(directory, exist_ok=True)

    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)

        if db.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
            db.executemany(
                """
                INSERT INTO products
                    (name, description, price, stock, category, image, rating)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                DEMO_PRODUCTS,
            )

        full_name, email, phone, password = DEMO_USER
        if db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone() is None:
            db.execute(
                """
                INSERT INTO users (full_name, email, phone, password)
                VALUES (?, ?, ?, ?)
                """,
                (full_name, email, phone, generate_password_hash(password)),
            )

        db.commit()
        close_db()
