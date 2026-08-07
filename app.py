import random
import smtplib
from email.mime.text import MIMEText
from config import EMAIL, EMAIL_PASSWORD
from flask import send_file
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph
from flask import Flask, render_template, request, redirect, send_file, send_file, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import razorpay

from config import (
    db,
    cursor,
    RAZORPAY_KEY_ID,
    RAZORPAY_KEY_SECRET
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

        hashed_password = generate_password_hash(password)

        sql = """
        INSERT INTO users(full_name,email,phone,password)
        VALUES(%s,%s,%s,%s)
        """

        values = (full_name, email, phone, hashed_password)

        cursor.execute(sql, values)
        db.commit()

        return redirect(url_for("login"))

    return render_template("register.html")


# ---------------- Login ----------------
@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        email = request.form["email"]
        password = request.form["password"]

        sql = "SELECT * FROM users WHERE email=%s"
        cursor.execute(sql, (email,))

        user = cursor.fetchone()

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

        sql = """
        INSERT INTO products(name, description, price, stock, image, category)
        VALUES(%s,%s,%s,%s,%s,%s)
        """

        values = (name, description, price, stock, filename, category)

        cursor.execute(sql, values)
        db.commit()

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

        email = request.form["email"]

        cursor.execute(
            "SELECT * FROM users WHERE email=%s",
            (email,)
        )

        user = cursor.fetchone()

        if user:

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

            hashed = generate_password_hash(new_password)

            cursor.execute(
                "UPDATE users SET password=%s WHERE email=%s",
                (
                    hashed,
                    session["reset_email"]
                )
            )

            db.commit()

            session.pop("otp", None)
            session.pop("reset_email", None)

            return redirect(url_for("login"))

        return "Invalid OTP"

    return render_template("reset_password.html")
@app.route("/product/<int:id>")
def product_details(id):

    # Product Details
    cursor.execute(
        "SELECT * FROM products WHERE id=%s",
        (id,)
    )
    product = cursor.fetchone()

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

    sql = """
    INSERT INTO cart(user_email, product_id, quantity)
    VALUES(%s, %s, %s)
    """

    values = (user_email, product_id, 1)

    cursor.execute(sql, values)
    db.commit()

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

    cursor.execute(sql, (cart_id,))
    db.commit()

    return redirect(url_for("cart"))
# ---------------- Increase Quantity ----------------
@app.route("/increase/<int:cart_id>")
def increase(cart_id):

    sql = "UPDATE cart SET quantity = quantity + 1 WHERE id=%s"

    cursor.execute(sql, (cart_id,))
    db.commit()

    return redirect(url_for("cart"))
# ---------------- Decrease Quantity ----------------
@app.route("/decrease/<int:cart_id>")
def decrease(cart_id):

    sql = """
    UPDATE cart
    SET quantity = quantity - 1
    WHERE id=%s AND quantity > 1
    """

    cursor.execute(sql, (cart_id,))
    db.commit()

    return redirect(url_for("cart"))

@app.route("/payment")
def payment():

    if "user" not in session:
        return redirect(url_for("login"))

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
def payment_success():

    if "user" not in session:
        return redirect(url_for("login"))

    payment_id = request.form.get("razorpay_payment_id")

    cursor.execute("""
        SELECT product_id, quantity
        FROM cart
        WHERE user_email=%s
    """, (session["user"],))

    cart_items = cursor.fetchall()

    for item in cart_items:

        product_id = item[0]
        quantity = item[1]

        cursor.execute(
            "SELECT price FROM products WHERE id=%s",
            (product_id,)
        )

        price = cursor.fetchone()[0]

        total = price * quantity

        cursor.execute("""
            INSERT INTO orders
            (user_email, product_id, quantity, total_price)
            VALUES(%s,%s,%s,%s)
        """, (
            session["user"],
            product_id,
            quantity,
            total
        ))

    cursor.execute(
        "DELETE FROM cart WHERE user_email=%s",
        (session["user"],)
    )

    db.commit()

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

    # Orders table me save karo
    for item in items:

        product_id = item[0]
        quantity = item[1]
        total_price = item[1] * item[2]

        sql = """
        INSERT INTO orders(user_email, product_id, quantity, total_price)
        VALUES(%s,%s,%s,%s)
        """

        cursor.execute(sql, (user_email, product_id, quantity, total_price))

    db.commit()

    # Cart Empty
    cursor.execute("DELETE FROM cart WHERE user_email=%s", (user_email,))
    db.commit()

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

        rating = request.form["rating"]
        review = request.form["review"]

        cursor.execute("""
            INSERT INTO reviews(user_email, product_id, rating, review)
            VALUES(%s,%s,%s,%s)
        """, (
            session["user"],
            product_id,
            rating,
            review
        ))

        db.commit()

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

    cursor.execute(
        "UPDATE orders SET order_status='Shipped' WHERE id=%s",
        (order_id,)
    )

    db.commit()

    return redirect(url_for("admin_orders"))


@app.route("/deliver-order/<int:order_id>")
def deliver_order(order_id):

    cursor.execute(
        "UPDATE orders SET order_status='Delivered' WHERE id=%s",
        (order_id,)
    )

    db.commit()

    return redirect(url_for("admin_orders"))
# ---------------- Edit Product ----------------
@app.route("/edit-product/<int:id>", methods=["GET", "POST"])
def edit_product(id):

    if request.method == "POST":

        name = request.form["name"]
        description = request.form["description"]
        price = request.form["price"]
        stock = request.form["stock"]

        sql = """
        UPDATE products
        SET name=%s,
            description=%s,
            price=%s,
            stock=%s
        WHERE id=%s
        """

        cursor.execute(sql, (name, description, price, stock, id))
        db.commit()

        return redirect(url_for("products"))

    cursor.execute("SELECT * FROM products WHERE id=%s", (id,))
    product = cursor.fetchone()

    return render_template("edit_product.html", product=product)
# ---------------- Delete Product ----------------
@app.route("/delete-product/<int:id>")
def delete_product(id):

    cursor.execute("DELETE FROM products WHERE id=%s", (id,))
    db.commit()

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

    cursor.execute("DELETE FROM wishlist WHERE id=%s", (id,))
    db.commit()

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

    return render_template("profile.html", user=user)
# ---------------- Edit Profile ----------------
@app.route("/edit-profile", methods=["GET", "POST"])
def edit_profile():

    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":

        full_name = request.form["full_name"]
        phone = request.form["phone"]

        sql = """
        UPDATE users
        SET full_name=%s,
            phone=%s
        WHERE email=%s
        """

        cursor.execute(sql, (full_name, phone, session["user"]))
        db.commit()

        return redirect(url_for("profile"))

    cursor.execute(
        "SELECT full_name, phone FROM users WHERE email=%s",
        (session["user"],)
    )

    user = cursor.fetchone()

    return render_template("edit_profile.html", user=user)

    from flask import send_file
from reportlab.pdfgen import canvas


@app.route("/invoice/<int:order_id>")
def invoice(order_id):

    filename = f"invoice_{order_id}.pdf"

    c = canvas.Canvas(filename)

    c.setFont("Helvetica-Bold", 18)
    c.drawString(180, 800, "E-Commerce Invoice")

    cursor.execute("""
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

    order = cursor.fetchone()

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