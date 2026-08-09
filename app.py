import logging
import os
import random
import smtplib
from contextlib import contextmanager
from email.mime.text import MIMEText

import mysql.connector
import razorpay
from flask import (
    Flask,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from reportlab.pdfgen import canvas
from werkzeug.exceptions import HTTPException
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from config import (
    EMAIL,
    EMAIL_PASSWORD,
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET,
    cursor,
    db,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "mysecretkey123")

if RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET:
    client = razorpay.Client(
        auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
    )
else:
    client = None

app.config["UPLOAD_FOLDER"] = "static/uploads"
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)


# ---------------- Error Handling Helpers ----------------
@contextmanager
def db_transaction():
    """Commit on success, roll back and re-raise on any failure."""
    try:
        yield cursor
        db.commit()
    except Exception:
        try:
            db.rollback()
        except mysql.connector.Error:
            logger.exception("Rollback failed")
        raise


def required_fields(*names):
    """Return stripped form values, aborting with 400 if any is missing."""
    values = []

    for name in names:
        value = (request.form.get(name) or "").strip()

        if not value:
            abort(400, description=f"Missing required field: {name}")

        values.append(value)

    return values


def parse_number(value, name, cast):
    try:
        return cast(value)
    except (TypeError, ValueError):
        abort(400, description=f"{name} must be a number")


@app.errorhandler(HTTPException)
def handle_http_error(error):
    return render_template(
        "error.html",
        code=error.code,
        message=error.description
    ), error.code


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    logger.exception("Unhandled error on %s", request.path, exc_info=error)

    return render_template(
        "error.html",
        code=500,
        message="Something went wrong. Please try again later."
    ), 500


# ---------------- Home ----------------
@app.route("/")
def home():

    if "user" in session:
        return render_template("index.html", user=session["user"])

    return render_template("index.html")


# ---------------- Register ----------------
@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        full_name, email, phone, password = required_fields(
            "full_name", "email", "phone", "password"
        )

        hashed_password = generate_password_hash(password)

        sql = """
        INSERT INTO users(full_name,email,phone,password)
        VALUES(%s,%s,%s,%s)
        """

        values = (full_name, email, phone, hashed_password)

        try:
            with db_transaction() as cur:
                cur.execute(sql, values)
        except mysql.connector.IntegrityError:
            logger.warning("Registration rejected for existing email %s", email)
            flash("An account with that email already exists.", "danger")

            return render_template("register.html"), 409

        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- Login ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email, password = required_fields("email", "password")

        sql = "SELECT * FROM users WHERE email=%s"
        cursor.execute(sql, (email,))

        user = cursor.fetchone()

        if user and check_password_hash(user[3], password):
            session["user"] = user[2]

            return redirect(url_for("home"))

        flash("Invalid email or password.", "danger")

        return render_template("login.html"), 401

    return render_template("login.html")


# ---------------- Logout ----------------
@app.route("/logout")
def logout():

    session.pop("user", None)

    return redirect(url_for("home"))


# ---------------- Add Product ----------------
@app.route("/add-product", methods=["GET", "POST"])
def add_product():

    if request.method == "POST":

        name, description, price, stock, category = required_fields(
            "name", "description", "price", "stock", "category"
        )

        price = parse_number(price, "price", float)
        stock = parse_number(stock, "stock", int)

        image = request.files.get("image")

        filename = ""

        if image and image.filename:
            filename = secure_filename(image.filename)

            if not filename:
                abort(400, description="Invalid image file name")

            try:
                image.save(
                    os.path.join(app.config["UPLOAD_FOLDER"], filename)
                )
            except OSError:
                logger.exception("Failed to save uploaded image %s", filename)
                abort(500, description="Could not save the uploaded image")

        sql = """
        INSERT INTO products(name, description, price, stock, image, category)
        VALUES(%s,%s,%s,%s,%s,%s)
        """

        values = (name, description, price, stock, filename, category)

        with db_transaction() as cur:
            cur.execute(sql, values)

        return redirect(url_for("products"))

    return render_template("add_product.html")


# ---------------- Products ----------------
@app.route("/products")
def products():

    search = request.args.get("search")

    if search:

        sql = """
        SELECT * FROM products
        WHERE name LIKE %s
        """

        cursor.execute(sql, ("%" + search + "%",))

    else:

        cursor.execute("SELECT * FROM products")

    products = cursor.fetchall()

    return render_template("products.html", products=products)

# ---------------- Forgot Password ----------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        (email,) = required_fields("email")

        cursor.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        user = cursor.fetchone()

        if not user:
            flash("No account found for that email.", "danger")

            return render_template("forgot_password.html"), 404

        if not (EMAIL and EMAIL_PASSWORD):
            logger.error("Password reset requested but email is not configured")
            abort(503, description="Password reset email is not configured")

        otp = random.randint(100000, 999999)

        msg = MIMEText(f"Your OTP is: {otp}")
        msg["Subject"] = "Password Reset OTP"
        msg["From"] = EMAIL
        msg["To"] = email

        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
                server.starttls()
                server.login(EMAIL, EMAIL_PASSWORD)
                server.send_message(msg)
        except (smtplib.SMTPException, OSError):
            logger.exception("Failed to send password reset OTP to %s", email)
            abort(502, description="Could not send the reset email. Try again later.")

        session["reset_email"] = email
        session["otp"] = str(otp)

        return redirect(url_for("reset_password"))

    return render_template("forgot_password.html")

# ---------------- Reset Password ----------------
@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():

    if request.method == "POST":

        otp, new_password = required_fields("otp", "password")

        expected_otp = session.get("otp")
        reset_email = session.get("reset_email")

        if not (expected_otp and reset_email):
            flash("Your reset session expired. Please request a new OTP.", "danger")

            return redirect(url_for("forgot_password"))

        if otp != expected_otp:
            flash("Invalid OTP.", "danger")

            return render_template("reset_password.html"), 400

        hashed = generate_password_hash(new_password)

        with db_transaction() as cur:
            cur.execute(
                "UPDATE users SET password=%s WHERE email=%s",
                (hashed, reset_email)
            )

        session.pop("otp", None)
        session.pop("reset_email", None)

        return redirect(url_for("login"))

    return render_template("reset_password.html")
@app.route("/product/<int:id>")
def product_details(id):

    # Product Details
    cursor.execute(
        "SELECT * FROM products WHERE id=%s",
        (id,)
    )
    product = cursor.fetchone()

    if product is None:
        abort(404, description="Product not found")

    # Product Reviews
    cursor.execute("""
        SELECT
            users.full_name,
            reviews.rating,
            reviews.review,
            reviews.created_at
        FROM reviews
        JOIN users
        ON reviews.user_email = users.email
        WHERE reviews.product_id = %s
        ORDER BY reviews.id DESC
    """, (id,))

    reviews = cursor.fetchall()

    return render_template(
        "product_details.html",
        product=product,
        reviews=reviews
    )
# ---------------- Add To Cart ----------------
@app.route("/add-to-cart/<int:product_id>")
def add_to_cart(product_id):

    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]

    cursor.execute("SELECT id FROM products WHERE id=%s", (product_id,))

    if cursor.fetchone() is None:
        abort(404, description="Product not found")

    sql = """
    INSERT INTO cart(user_email, product_id, quantity)
    VALUES(%s, %s, %s)
    """

    values = (user_email, product_id, 1)

    with db_transaction() as cur:
        cur.execute(sql, values)

    return redirect(url_for("cart"))
# ---------------- Cart ----------------
# ---------------- Cart ----------------
@app.route("/cart")
def cart():

    if "user" not in session:
        return redirect(url_for("login"))

    sql = """
    SELECT
        cart.id,
        products.name,
        products.price,
        products.image,
        cart.quantity
    FROM cart
    JOIN products
    ON cart.product_id = products.id
    WHERE cart.user_email = %s
    """

    cursor.execute(sql, (session["user"],))
    items = cursor.fetchall()
    total = 0

    for item in items:
        total += item[2] * item[4]

    return render_template("cart.html", items=items)


# ---------------- Remove From Cart ----------------
@app.route("/remove-cart/<int:cart_id>")
def remove_cart(cart_id):

    sql = "DELETE FROM cart WHERE id=%s"

    with db_transaction() as cur:
        cur.execute(sql, (cart_id,))

    return redirect(url_for("cart"))
# ---------------- Increase Quantity ----------------
@app.route("/increase/<int:cart_id>")
def increase(cart_id):

    sql = "UPDATE cart SET quantity = quantity + 1 WHERE id=%s"

    with db_transaction() as cur:
        cur.execute(sql, (cart_id,))

    return redirect(url_for("cart"))
# ---------------- Decrease Quantity ----------------
@app.route("/decrease/<int:cart_id>")
def decrease(cart_id):

    sql = """
    UPDATE cart
    SET quantity = quantity - 1
    WHERE id=%s AND quantity > 1
    """

    with db_transaction() as cur:
        cur.execute(sql, (cart_id,))

    return redirect(url_for("cart"))

@app.route("/payment")
def payment():

    if "user" not in session:
        return redirect(url_for("login"))

    if client is None:
        logger.error("Payment requested but Razorpay credentials are not set")
        abort(503, description="Payments are not configured")

    amount = 500 * 100   # ₹500 (Razorpay paise me amount leta hai)

    try:
        order = client.order.create({
            "amount": amount,
            "currency": "INR",
            "payment_capture": 1
        })
    except Exception:
        logger.exception("Razorpay order creation failed")
        abort(502, description="Could not start the payment. Please try again.")

    return render_template(
        "payment.html",
        order=order,
        key_id=RAZORPAY_KEY_ID
    )
# ---------------- Payment Success ----------------
@app.route("/payment-success", methods=["POST"])
def payment_success():

    if "user" not in session:
        return redirect(url_for("login"))

    payment_id = request.form.get("razorpay_payment_id")

    if not payment_id:
        abort(400, description="Missing Razorpay payment id")

    cursor.execute("""
        SELECT product_id, quantity
        FROM cart
        WHERE user_email=%s
    """, (session["user"],))

    cart_items = cursor.fetchall()

    # Orders and cart clearing must succeed or fail together.
    with db_transaction() as cur:

        for item in cart_items:

            product_id = item[0]
            quantity = item[1]

            cur.execute(
                "SELECT price FROM products WHERE id=%s",
                (product_id,)
            )

            row = cur.fetchone()

            if row is None:
                logger.error(
                    "Cart references missing product %s for user %s",
                    product_id,
                    session["user"]
                )
                abort(409, description="A product in your cart no longer exists")

            total = row[0] * quantity

            cur.execute("""
                INSERT INTO orders
                (user_email, product_id, quantity, total_price)
                VALUES(%s,%s,%s,%s)
            """, (
                session["user"],
                product_id,
                quantity,
                total
            ))

        cur.execute(
            "DELETE FROM cart WHERE user_email=%s",
            (session["user"],)
        )

    return render_template(
        "success.html",
        payment_id=payment_id
    )
    # ---------------- Checkout ----------------
@app.route("/checkout")
def checkout():

    if "user" not in session:
        return redirect(url_for("login"))

    return render_template("checkout.html")
# ---------------- Place Order ----------------
@app.route("/place-order")
def place_order():

    if "user" not in session:
        return redirect(url_for("login"))

    user_email = session["user"]

    # Cart ke products nikalo
    sql = """
    SELECT
        cart.product_id,
        cart.quantity,
        products.price
    FROM cart
    JOIN products
    ON cart.product_id = products.id
    WHERE cart.user_email=%s
    """

    cursor.execute(sql, (user_email,))
    items = cursor.fetchall()

    if not items:
        flash("Your cart is empty.", "warning")

        return redirect(url_for("cart"))

    insert_sql = """
    INSERT INTO orders(user_email, product_id, quantity, total_price)
    VALUES(%s,%s,%s,%s)
    """

    # Orders and cart clearing must succeed or fail together.
    with db_transaction() as cur:

        for item in items:

            product_id = item[0]
            quantity = item[1]
            total_price = item[1] * item[2]

            cur.execute(
                insert_sql,
                (user_email, product_id, quantity, total_price)
            )

        cur.execute("DELETE FROM cart WHERE user_email=%s", (user_email,))

    return redirect(url_for("orders"))
# ---------------- Orders ----------------
@app.route("/orders")
def orders():

    if "user" not in session:
        return redirect(url_for("login"))

    sql = """
SELECT
    orders.id,
    products.id,
    products.name,
    orders.quantity,
    orders.total_price,
    orders.order_date
FROM orders
JOIN products
ON orders.product_id = products.id
WHERE orders.user_email=%s
ORDER BY orders.id DESC
"""

    cursor.execute(sql, (session["user"],))

    orders_data = cursor.fetchall()

    return render_template(
        "orders.html",
        orders=orders_data
    )
@app.route("/review/<int:product_id>", methods=["GET", "POST"])
def review(product_id):

    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        rating, review = required_fields("rating", "review")
        rating = parse_number(rating, "rating", int)

        if not 1 <= rating <= 5:
            abort(400, description="Rating must be between 1 and 5")

        with db_transaction() as cur:
            cur.execute("""
                INSERT INTO reviews(user_email, product_id, rating, review)
                VALUES(%s,%s,%s,%s)
            """, (
                session["user"],
                product_id,
                rating,
                review
            ))

        return redirect(url_for("orders"))

    return render_template(
        "review.html",
        product_id=product_id
    )
# ---------------- Admin Dashboard ----------------
@app.route("/admin")
def admin():

    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM products")
    total_products = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM orders")
    total_orders = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(total_price) FROM orders")
    revenue = cursor.fetchone()[0]

    if revenue is None:
        revenue = 0

    return render_template(
        "admin.html",
        total_users=total_users,
        total_products=total_products,
        total_orders=total_orders,
        revenue=revenue
    )
@app.route("/admin/orders")
def admin_orders():

    cursor.execute("""
    SELECT
        orders.id,
        users.full_name,
        products.name,
        orders.quantity,
        orders.total_price,
        orders.payment_status,
        orders.order_status,
        orders.order_date
    FROM orders
    JOIN products
    ON orders.product_id = products.id
    JOIN users
    ON orders.user_email = users.email
    ORDER BY orders.id DESC
    """)

    orders = cursor.fetchall()

    return render_template(
        "admin_orders.html",
        orders=orders
    )
@app.route("/ship-order/<int:order_id>")
def ship_order(order_id):

    with db_transaction() as cur:
        cur.execute(
            "UPDATE orders SET order_status='Shipped' WHERE id=%s",
            (order_id,)
        )

        if cur.rowcount == 0:
            abort(404, description="Order not found")

    return redirect(url_for("admin_orders"))


@app.route("/deliver-order/<int:order_id>")
def deliver_order(order_id):

    with db_transaction() as cur:
        cur.execute(
            "UPDATE orders SET order_status='Delivered' WHERE id=%s",
            (order_id,)
        )

        if cur.rowcount == 0:
            abort(404, description="Order not found")

    return redirect(url_for("admin_orders"))
# ---------------- Edit Product ----------------
@app.route("/edit-product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    if request.method == "POST":

        name, description, price, stock = required_fields(
            "name", "description", "price", "stock"
        )

        price = parse_number(price, "price", float)
        stock = parse_number(stock, "stock", int)

        sql = """
        UPDATE products
        SET name=%s,
            description=%s,
            price=%s,
            stock=%s
        WHERE id=%s
        """

        with db_transaction() as cur:
            cur.execute(sql, (name, description, price, stock, id))

            if cur.rowcount == 0:
                abort(404, description="Product not found")

        return redirect(url_for("products"))

    cursor.execute("SELECT * FROM products WHERE id=%s", (id,))
    product = cursor.fetchone()

    if product is None:
        abort(404, description="Product not found")

    return render_template("edit_product.html", product=product)
# ---------------- Delete Product ----------------
@app.route("/delete-product/<int:id>")
def delete_product(id):

    with db_transaction() as cur:
        cur.execute("DELETE FROM products WHERE id=%s", (id,))

        if cur.rowcount == 0:
            abort(404, description="Product not found")

    return redirect(url_for("products"))
# ---------------- Wishlist ----------------
@app.route("/wishlist")
def wishlist():

    if "user" not in session:
        return redirect(url_for("login"))

    sql = """
    SELECT
        wishlist.id,
        products.id,
        products.name,
        products.price,
        products.image
    FROM wishlist
    JOIN products
    ON wishlist.product_id = products.id
    WHERE wishlist.user_email=%s
    """

    cursor.execute(sql, (session["user"],))
    items = cursor.fetchall()

    return render_template("wishlist.html", items=items)
# ---------------- Remove Wishlist ----------------
@app.route("/remove-wishlist/<int:id>")
def remove_wishlist(id):

    with db_transaction() as cur:
        cur.execute("DELETE FROM wishlist WHERE id=%s", (id,))

    return redirect(url_for("wishlist"))
# ---------------- Profile ----------------
@app.route("/profile")
def profile():

    if "user" not in session:
        return redirect(url_for("login"))

    cursor.execute(
        "SELECT full_name,email,phone FROM users WHERE email=%s",
        (session["user"],)
    )

    user = cursor.fetchone()

    if user is None:
        logger.warning("Session user %s no longer exists", session["user"])
        session.pop("user", None)

        return redirect(url_for("login"))

    return render_template("profile.html", user=user)
# ---------------- Edit Profile ----------------
@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():

    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        full_name, phone = required_fields("full_name", "phone")

        sql = """
        UPDATE users
        SET full_name=%s,
            phone=%s
        WHERE email=%s
        """

        with db_transaction() as cur:
            cur.execute(sql, (full_name, phone, session["user"]))

        return redirect(url_for("profile"))

    cursor.execute(
        "SELECT full_name, phone FROM users WHERE email=%s",
        (session["user"],)
    )

    user = cursor.fetchone()

    if user is None:
        logger.warning("Session user %s no longer exists", session["user"])
        session.pop("user", None)

        return redirect(url_for("login"))

    return render_template("edit_profile.html", user=user)


@app.route("/invoice/<int:order_id>")
def invoice(order_id):

    if "user" not in session:
        return redirect(url_for("login"))

    cursor.execute("""
        SELECT
            products.name,
            orders.quantity,
            orders.total_price,
            orders.order_date
        FROM orders
        JOIN products
        ON orders.product_id = products.id
        WHERE orders.id=%s AND orders.user_email=%s
    """, (order_id, session["user"]))

    order = cursor.fetchone()

    if order is None:
        abort(404, description="Order not found")

    filename = f"invoice_{order_id}.pdf"

    try:
        c = canvas.Canvas(filename)

        c.setFont("Helvetica-Bold", 18)
        c.drawString(180, 800, "E-Commerce Invoice")

        c.setFont("Helvetica", 14)

        c.drawString(50, 730, f"Product : {order[0]}")
        c.drawString(50, 700, f"Quantity : {order[1]}")
        c.drawString(50, 670, f"Total : ₹{order[2]}")
        c.drawString(50, 640, f"Date : {order[3]}")

        c.save()
    except OSError:
        logger.exception("Failed to generate invoice for order %s", order_id)
        abort(500, description="Could not generate the invoice")

    return send_file(filename, as_attachment=True)


# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)
