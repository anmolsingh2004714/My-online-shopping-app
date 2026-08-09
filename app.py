import os
import random
import smtplib
from email.mime.text import MIMEText

import razorpay
from flask import Flask, redirect, render_template, request, send_file, session, url_for
from reportlab.pdfgen import canvas
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from auth import login_required
from config import EMAIL, EMAIL_PASSWORD, RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET
from db_utils import execute, fetch_all, fetch_one, fetch_value
from services import (
    cart_total,
    create_orders_from_cart,
    get_cart_items,
    get_user_by_email,
    set_order_status
)

app = Flask(__name__)
app.secret_key = "mysecretkey123"
client = razorpay.Client(
    auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET)
)

app.config["UPLOAD_FOLDER"] = "static/uploads"

print("✅ Database Connected Successfully")


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

        full_name = request.form["full_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        password = request.form["password"]

        execute(
            """
            INSERT INTO users(full_name,email,phone,password)
            VALUES(%s,%s,%s,%s)
            """,
            (full_name, email, phone, generate_password_hash(password))
        )

        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- Login ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        user = get_user_by_email(email)

        if user:

            if check_password_hash(user[3], password):
                session["user"] = user[2]
                return redirect(url_for("home"))

            else:
                return "Wrong Password"

        else:
            return "Email Not Found"

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

        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        stock = request.form["stock"]
        category = request.form["category"]

        image = request.files["image"]

        filename = ""

        if image and image.filename != "":
            filename = secure_filename(image.filename)
            image.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        execute(
            """
            INSERT INTO products(name, description, price, stock, image, category)
            VALUES(%s,%s,%s,%s,%s,%s)
            """,
            (name, description, price, stock, filename, category)
        )

        return redirect(url_for("products"))

    return render_template("add_product.html")


# ---------------- Products ----------------
@app.route("/products")
def products():

    search = request.args.get("search")

    if search:
        products = fetch_all(
            "SELECT * FROM products WHERE name LIKE %s",
            ("%" + search + "%",)
        )

    else:
        products = fetch_all("SELECT * FROM products")

    return render_template("products.html", products=products)


# ---------------- Forgot Password ----------------
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():

    if request.method == "POST":

        email = request.form["email"]

        if get_user_by_email(email):

            otp = random.randint(100000, 999999)

            session["reset_email"] = email
            session["otp"] = str(otp)

            msg = MIMEText(f"Your OTP is: {otp}")
            msg["Subject"] = "Password Reset OTP"
            msg["From"] = EMAIL
            msg["To"] = email

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(EMAIL, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()

            return redirect(url_for("reset_password"))

        return "Email not found"

    return render_template("forgot_password.html")


# ---------------- Reset Password ----------------
@app.route("/reset-password", methods=["GET", "POST"])
def reset_password():

    if request.method == "POST":

        otp = request.form["otp"]
        new_password = request.form["password"]

        if otp == session.get("otp"):

            execute(
                "UPDATE users SET password=%s WHERE email=%s",
                (
                    generate_password_hash(new_password),
                    session["reset_email"]
                )
            )

            session.pop("otp", None)
            session.pop("reset_email", None)

            return redirect(url_for("login"))

        return "Invalid OTP"

    return render_template("reset_password.html")


# ---------------- Product Details ----------------
@app.route("/product/<int:id>")
def product_details(id):

    product = fetch_one("SELECT * FROM products WHERE id=%s", (id,))

    reviews = fetch_all("""
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

    return render_template(
        "product_details.html",
        product=product,
        reviews=reviews
    )


# ---------------- Add To Cart ----------------
@app.route("/add-to-cart/<int:product_id>")
@login_required
def add_to_cart(product_id):

    execute(
        """
        INSERT INTO cart(user_email, product_id, quantity)
        VALUES(%s, %s, %s)
        """,
        (session["user"], product_id, 1)
    )

    return redirect(url_for("cart"))


# ---------------- Cart ----------------
@app.route("/cart")
@login_required
def cart():

    items = get_cart_items(session["user"])

    return render_template(
        "cart.html",
        items=items,
        total=cart_total(items)
    )


# ---------------- Remove From Cart ----------------
@app.route("/remove-cart/<int:cart_id>")
def remove_cart(cart_id):

    execute("DELETE FROM cart WHERE id=%s", (cart_id,))

    return redirect(url_for("cart"))


# ---------------- Increase Quantity ----------------
@app.route("/increase/<int:cart_id>")
def increase(cart_id):

    execute(
        "UPDATE cart SET quantity = quantity + 1 WHERE id=%s",
        (cart_id,)
    )

    return redirect(url_for("cart"))


# ---------------- Decrease Quantity ----------------
@app.route("/decrease/<int:cart_id>")
def decrease(cart_id):

    execute(
        """
        UPDATE cart
        SET quantity = quantity - 1
        WHERE id=%s AND quantity > 1
        """,
        (cart_id,)
    )

    return redirect(url_for("cart"))


# ---------------- Payment ----------------
@app.route("/payment")
@login_required
def payment():

    amount = 500 * 100   # ₹500 (Razorpay paise me amount leta hai)

    order = client.order.create({
        "amount": amount,
        "currency": "INR",
        "payment_capture": 1
    })

    return render_template(
        "payment.html",
        order=order,
        key_id=RAZORPAY_KEY_ID
    )


# ---------------- Payment Success ----------------
@app.route("/payment-success", methods=["POST"])
@login_required
def payment_success():

    payment_id = request.form.get("razorpay_payment_id")

    create_orders_from_cart(session["user"])

    return render_template(
        "success.html",
        payment_id=payment_id
    )


# ---------------- Checkout ----------------
@app.route("/checkout")
@login_required
def checkout():

    return render_template("checkout.html")


# ---------------- Place Order ----------------
@app.route("/place-order")
@login_required
def place_order():

    create_orders_from_cart(session["user"])

    return redirect(url_for("orders"))


# ---------------- Orders ----------------
@app.route("/orders")
@login_required
def orders():

    orders_data = fetch_all("""
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
    """, (session["user"],))

    return render_template(
        "orders.html",
        orders=orders_data
    )


# ---------------- Review ----------------
@app.route("/review/<int:product_id>", methods=["GET", "POST"])
@login_required
def review(product_id):

    if request.method == "POST":

        rating = request.form["rating"]
        review = request.form["review"]

        execute(
            """
            INSERT INTO reviews(user_email, product_id, rating, review)
            VALUES(%s,%s,%s,%s)
            """,
            (session["user"], product_id, rating, review)
        )

        return redirect(url_for("orders"))

    return render_template(
        "review.html",
        product_id=product_id
    )


# ---------------- Admin Dashboard ----------------
@app.route("/admin")
def admin():

    return render_template(
        "admin.html",
        total_users=fetch_value("SELECT COUNT(*) FROM users", default=0),
        total_products=fetch_value("SELECT COUNT(*) FROM products", default=0),
        total_orders=fetch_value("SELECT COUNT(*) FROM orders", default=0),
        revenue=fetch_value("SELECT SUM(total_price) FROM orders", default=0)
    )


@app.route("/admin/orders")
def admin_orders():

    orders = fetch_all("""
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

    return render_template(
        "admin_orders.html",
        orders=orders
    )


@app.route("/ship-order/<int:order_id>")
def ship_order(order_id):

    set_order_status(order_id, "Shipped")

    return redirect(url_for("admin_orders"))


@app.route("/deliver-order/<int:order_id>")
def deliver_order(order_id):

    set_order_status(order_id, "Delivered")

    return redirect(url_for("admin_orders"))


# ---------------- Edit Product ----------------
@app.route("/edit-product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    if request.method == "POST":

        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        stock = request.form["stock"]

        execute(
            """
            UPDATE products
            SET name=%s,
                description=%s,
                price=%s,
                stock=%s
            WHERE id=%s
            """,
            (name, description, price, stock, id)
        )

        return redirect(url_for("products"))

    product = fetch_one("SELECT * FROM products WHERE id=%s", (id,))

    return render_template("edit_product.html", product=product)


# ---------------- Delete Product ----------------
@app.route("/delete-product/<int:id>")
def delete_product(id):

    execute("DELETE FROM products WHERE id=%s", (id,))

    return redirect(url_for("products"))


# ---------------- Wishlist ----------------
@app.route("/wishlist")
@login_required
def wishlist():

    items = fetch_all("""
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
    """, (session["user"],))

    return render_template("wishlist.html", items=items)


# ---------------- Remove Wishlist ----------------
@app.route("/remove-wishlist/<int:id>")
def remove_wishlist(id):

    execute("DELETE FROM wishlist WHERE id=%s", (id,))

    return redirect(url_for("wishlist"))


# ---------------- Profile ----------------
@app.route("/profile")
@login_required
def profile():

    user = get_user_by_email(session["user"], "full_name,email,phone")

    return render_template("profile.html", user=user)


# ---------------- Edit Profile ----------------
@app.route("/edit-profile", methods=["GET", "POST"])
@login_required
def edit_profile():

    if request.method == "POST":

        full_name = request.form["full_name"]
        phone = request.form["phone"]

        execute(
            """
            UPDATE users
            SET full_name=%s,
                phone=%s
            WHERE email=%s
            """,
            (full_name, phone, session["user"])
        )

        return redirect(url_for("profile"))

    user = get_user_by_email(session["user"], "full_name, phone")

    return render_template("edit_profile.html", user=user)


# ---------------- Invoice ----------------
@app.route("/invoice/<int:order_id>")
def invoice(order_id):

    filename = f"invoice_{order_id}.pdf"

    c = canvas.Canvas(filename)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(180, 800, "E-Commerce Invoice")

    order = fetch_one("""
        SELECT
            products.name,
            orders.quantity,
            orders.total_price,
            orders.order_date
        FROM orders
        JOIN products
        ON orders.product_id = products.id
        WHERE orders.id=%s
    """, (order_id,))

    c.setFont("Helvetica", 14)

    c.drawString(50, 730, f"Product : {order[0]}")
    c.drawString(50, 700, f"Quantity : {order[1]}")
    c.drawString(50, 670, f"Total : ₹{order[2]}")
    c.drawString(50, 640, f"Date : {order[3]}")

    c.save()

    return send_file(filename, as_attachment=True)


# ---------------- Run ----------------
if __name__ == "__main__":
    app.run(debug=True)
