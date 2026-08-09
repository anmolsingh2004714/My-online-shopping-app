"""ShopKart — a small responsive Flask + Tailwind e-commerce demo store.

Run with::

    pip install -r requirements.txt
    flask --app app run --debug
"""

import os

from db import close_db, get_db, init_db
from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash

CATEGORY_ALL = "All"


def create_app(database=None):
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-secret-change-me"),
        DATABASE=database
        or os.getenv("DATABASE", os.path.join(app.instance_path, "shopkart.sqlite3")),
    )

    app.teardown_appcontext(close_db)
    init_db(app)
    register_routes(app)

    return app


def current_user():
    """Return the logged in user row, or ``None``."""

    user_id = session.get("user_id")
    if user_id is None:
        return None

    return get_db().execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(view):
    """Redirect anonymous visitors to the login page."""

    def wrapped(*args, **kwargs):
        if current_user() is None:
            flash("Please sign in to continue.", "error")
            return redirect(url_for("login", next=request.path))

        return view(*args, **kwargs)

    wrapped.__name__ = view.__name__
    return wrapped


def cart_rows():
    user = current_user()
    if user is None:
        return []

    return (
        get_db()
        .execute(
            """
            SELECT
                cart_items.id,
                cart_items.quantity,
                products.id AS product_id,
                products.name,
                products.price,
                products.image,
                products.stock
            FROM cart_items
            JOIN products ON products.id = cart_items.product_id
            WHERE cart_items.user_id = ?
            ORDER BY cart_items.id
            """,
            (user["id"],),
        )
        .fetchall()
    )


def cart_summary(items):
    """Return subtotal, shipping and grand total for the given cart rows."""

    subtotal = sum(item["price"] * item["quantity"] for item in items)
    shipping = 0.0 if subtotal == 0 or subtotal >= 2000 else 99.0

    return {
        "subtotal": subtotal,
        "shipping": shipping,
        "total": subtotal + shipping,
        "count": sum(item["quantity"] for item in items),
    }


def register_routes(app):
    @app.template_filter("rupees")
    def rupees(amount):
        return f"₹{amount:,.0f}"

    @app.context_processor
    def inject_globals():
        items = cart_rows()
        return {
            "user": current_user(),
            "cart_count": cart_summary(items)["count"],
        }

    @app.route("/")
    def home():
        db = get_db()
        featured = db.execute(
            "SELECT * FROM products ORDER BY rating DESC LIMIT 4"
        ).fetchall()
        categories = [
            row["category"]
            for row in db.execute(
                "SELECT DISTINCT category FROM products ORDER BY category"
            ).fetchall()
        ]

        return render_template("index.html", featured=featured, categories=categories)

    @app.route("/products")
    def products():
        db = get_db()
        search = (request.args.get("search") or "").strip()
        category = request.args.get("category") or CATEGORY_ALL
        sort = request.args.get("sort") or "featured"

        sql = "SELECT * FROM products WHERE 1 = 1"
        params = []

        if search:
            sql += " AND (name LIKE ? OR description LIKE ?)"
            params += [f"%{search}%", f"%{search}%"]

        if category != CATEGORY_ALL:
            sql += " AND category = ?"
            params.append(category)

        sql += {
            "price-asc": " ORDER BY price ASC",
            "price-desc": " ORDER BY price DESC",
            "name": " ORDER BY name ASC",
        }.get(sort, " ORDER BY rating DESC")

        catalogue = db.execute(sql, params).fetchall()
        categories = [CATEGORY_ALL] + [
            row["category"]
            for row in db.execute(
                "SELECT DISTINCT category FROM products ORDER BY category"
            ).fetchall()
        ]

        return render_template(
            "products.html",
            products=catalogue,
            categories=categories,
            search=search,
            active_category=category,
            sort=sort,
        )

    @app.route("/product/<int:product_id>")
    def product_details(product_id):
        db = get_db()
        product = db.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()

        if product is None:
            return render_template("404.html"), 404

        related = db.execute(
            "SELECT * FROM products WHERE category = ? AND id != ? LIMIT 3",
            (product["category"], product_id),
        ).fetchall()

        return render_template("product_details.html", product=product, related=related)

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            email = request.form.get("email", "").strip().lower()
            phone = request.form.get("phone", "").strip()
            password = request.form.get("password", "")

            db = get_db()

            if not full_name or not email or len(password) < 8:
                flash("Name, email and an 8+ character password are required.", "error")
            elif db.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
                flash("That email is already registered.", "error")
            else:
                cursor = db.execute(
                    """
                    INSERT INTO users (full_name, email, phone, password)
                    VALUES (?, ?, ?, ?)
                    """,
                    (full_name, email, phone, generate_password_hash(password)),
                )
                db.commit()
                session["user_id"] = cursor.lastrowid
                flash(f"Welcome to ShopKart, {full_name}!", "success")
                return redirect(url_for("home"))

        return render_template("register.html")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")

            user = (
                get_db()
                .execute("SELECT * FROM users WHERE email = ?", (email,))
                .fetchone()
            )

            if user is None or not check_password_hash(user["password"], password):
                flash("Invalid email or password.", "error")
            else:
                session["user_id"] = user["id"]
                flash(f"Signed in as {user['full_name']}.", "success")
                return redirect(request.args.get("next") or url_for("home"))

        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.pop("user_id", None)
        flash("You have been signed out.", "success")
        return redirect(url_for("home"))

    @app.route("/cart")
    @login_required
    def cart():
        items = cart_rows()
        return render_template("cart.html", items=items, summary=cart_summary(items))

    @app.route("/cart/add/<int:product_id>", methods=["POST"])
    @login_required
    def add_to_cart(product_id):
        db = get_db()
        product = db.execute(
            "SELECT * FROM products WHERE id = ?", (product_id,)
        ).fetchone()

        if product is None:
            return render_template("404.html"), 404

        quantity = max(1, request.form.get("quantity", type=int) or 1)

        db.execute(
            """
            INSERT INTO cart_items (user_id, product_id, quantity)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id, product_id)
            DO UPDATE SET quantity = MIN(quantity + ?, ?)
            """,
            (session["user_id"], product_id, quantity, quantity, product["stock"]),
        )
        db.commit()

        flash(f"{product['name']} added to your cart.", "success")
        return redirect(request.form.get("next") or url_for("cart"))

    @app.route("/cart/update/<int:item_id>", methods=["POST"])
    @login_required
    def update_cart(item_id):
        db = get_db()
        delta = request.form.get("delta", type=int) or 0

        db.execute(
            """
            UPDATE cart_items
            SET quantity = MAX(
                1,
                MIN(
                    quantity + ?,
                    (SELECT stock FROM products WHERE id = cart_items.product_id)
                )
            )
            WHERE id = ? AND user_id = ?
            """,
            (delta, item_id, session["user_id"]),
        )
        db.commit()

        return redirect(url_for("cart"))

    @app.route("/cart/remove/<int:item_id>", methods=["POST"])
    @login_required
    def remove_from_cart(item_id):
        db = get_db()
        db.execute(
            "DELETE FROM cart_items WHERE id = ? AND user_id = ?",
            (item_id, session["user_id"]),
        )
        db.commit()

        flash("Item removed from your cart.", "success")
        return redirect(url_for("cart"))

    @app.route("/checkout", methods=["GET", "POST"])
    @login_required
    def checkout():
        items = cart_rows()
        summary = cart_summary(items)

        if not items:
            flash("Your cart is empty.", "error")
            return redirect(url_for("products"))

        if request.method == "POST":
            address = request.form.get("address", "").strip()

            if not address:
                flash("A delivery address is required.", "error")
            else:
                db = get_db()
                cursor = db.execute(
                    "INSERT INTO orders (user_id, total, address) VALUES (?, ?, ?)",
                    (session["user_id"], summary["total"], address),
                )
                order_id = cursor.lastrowid

                db.executemany(
                    """
                    INSERT INTO order_items
                        (order_id, product_id, name, price, quantity)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            order_id,
                            item["product_id"],
                            item["name"],
                            item["price"],
                            item["quantity"],
                        )
                        for item in items
                    ],
                )
                db.execute(
                    "DELETE FROM cart_items WHERE user_id = ?", (session["user_id"],)
                )
                db.commit()

                return redirect(url_for("order_confirmation", order_id=order_id))

        return render_template("checkout.html", items=items, summary=summary)

    @app.route("/orders")
    @login_required
    def orders():
        rows = (
            get_db()
            .execute(
                """
                SELECT
                    orders.id,
                    orders.total,
                    orders.address,
                    orders.placed_at,
                    COUNT(order_items.id) AS lines
                FROM orders
                LEFT JOIN order_items ON order_items.order_id = orders.id
                WHERE orders.user_id = ?
                GROUP BY orders.id
                ORDER BY orders.id DESC
                """,
                (session["user_id"],),
            )
            .fetchall()
        )

        return render_template("orders.html", orders=rows)

    @app.route("/orders/<int:order_id>")
    @login_required
    def order_confirmation(order_id):
        db = get_db()
        order = db.execute(
            "SELECT * FROM orders WHERE id = ? AND user_id = ?",
            (order_id, session["user_id"]),
        ).fetchone()

        if order is None:
            return render_template("404.html"), 404

        items = db.execute(
            "SELECT * FROM order_items WHERE order_id = ?", (order_id,)
        ).fetchall()

        return render_template("order_confirmation.html", order=order, items=items)

    @app.errorhandler(404)
    def not_found(error):
        return render_template("404.html"), 404


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
