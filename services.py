from db_utils import execute, fetch_all, fetch_one

CART_ITEMS_SQL = """
SELECT
    cart.id,
    products.name,
    products.price,
    products.image,
    cart.quantity,
    cart.product_id
FROM cart
JOIN products
ON cart.product_id = products.id
WHERE cart.user_email = %s
"""


def get_cart_items(user_email):
    return fetch_all(CART_ITEMS_SQL, (user_email,))


def cart_total(items):
    return sum(item[2] * item[4] for item in items)


def clear_cart(user_email):
    execute("DELETE FROM cart WHERE user_email=%s", (user_email,))


def create_orders_from_cart(user_email):
    for item in get_cart_items(user_email):

        product_id = item[5]
        quantity = item[4]
        total_price = item[2] * quantity

        execute(
            """
            INSERT INTO orders(user_email, product_id, quantity, total_price)
            VALUES(%s,%s,%s,%s)
            """,
            (user_email, product_id, quantity, total_price)
        )

    clear_cart(user_email)


def get_user_by_email(email, columns="*"):
    return fetch_one(
        f"SELECT {columns} FROM users WHERE email=%s",
        (email,)
    )


def set_order_status(order_id, status):
    execute(
        "UPDATE orders SET order_status=%s WHERE id=%s",
        (status, order_id)
    )
