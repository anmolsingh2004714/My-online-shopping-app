"""Cart maths, cart mutations and the checkout flow."""

from app import cart_summary


def make_items(rows):
    return [{"price": price, "quantity": quantity} for price, quantity in rows]


def test_cart_summary_of_empty_cart_is_free():
    assert cart_summary([]) == {
        "subtotal": 0,
        "shipping": 0.0,
        "total": 0,
        "count": 0,
    }


def test_cart_summary_charges_shipping_below_threshold():
    summary = cart_summary(make_items([(500.0, 2)]))

    assert summary["subtotal"] == 1000.0
    assert summary["shipping"] == 99.0
    assert summary["total"] == 1099.0
    assert summary["count"] == 2


def test_cart_summary_ships_free_at_threshold():
    summary = cart_summary(make_items([(1000.0, 2)]))

    assert summary["shipping"] == 0.0
    assert summary["total"] == 2000.0


def test_empty_cart_shows_empty_state(auth_client):
    body = auth_client.get("/cart").get_data(as_text=True)

    assert "Your cart is empty" in body


def test_add_to_cart_then_view_totals(auth_client):
    auth_client.post("/cart/add/2", data={"quantity": 2})

    body = auth_client.get("/cart").get_data(as_text=True)

    assert "Pulse Gaming Mouse" in body
    assert "₹2,998" in body  # 1499 x 2
    assert "Free" in body  # above the free shipping threshold


def test_adding_same_product_twice_merges_quantity(auth_client):
    auth_client.post("/cart/add/2", data={"quantity": 1})
    auth_client.post("/cart/add/2", data={"quantity": 3})

    body = auth_client.get("/cart").get_data(as_text=True)

    assert body.count("/cart/remove/") == 1  # one cart line, not two
    assert "₹5,996" in body  # 1499 x 4


def test_add_to_cart_rejects_unknown_product(auth_client):
    assert auth_client.post("/cart/add/999", data={"quantity": 1}).status_code == 404


def test_quantity_can_be_increased_and_never_drops_below_one(auth_client):
    auth_client.post("/cart/add/2", data={"quantity": 1})

    auth_client.post("/cart/update/1", data={"delta": 1})
    assert "₹2,998" in auth_client.get("/cart").get_data(as_text=True)

    auth_client.post("/cart/update/1", data={"delta": -5})
    assert "₹1,499" in auth_client.get("/cart").get_data(as_text=True)


def test_remove_from_cart_empties_it(auth_client):
    auth_client.post("/cart/add/2", data={"quantity": 1})

    response = auth_client.post("/cart/remove/1", follow_redirects=True)
    body = response.get_data(as_text=True)

    assert "Item removed from your cart." in body
    assert "Your cart is empty" in body


def test_checkout_with_empty_cart_redirects_to_shop(auth_client):
    response = auth_client.get("/checkout")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/products")


def test_checkout_page_lists_cart_items(auth_client):
    auth_client.post("/cart/add/1", data={"quantity": 1})

    body = auth_client.get("/checkout").get_data(as_text=True)

    assert "Aurora Wireless Headphones" in body
    assert "Place order" in body


def test_checkout_requires_an_address(auth_client):
    auth_client.post("/cart/add/1", data={"quantity": 1})

    response = auth_client.post("/checkout", data={"address": "  "})

    assert "A delivery address is required." in response.get_data(as_text=True)
    assert "Aurora Wireless Headphones" in auth_client.get("/cart").get_data(as_text=True)


def test_placing_an_order_stores_it_and_clears_the_cart(auth_client):
    auth_client.post("/cart/add/1", data={"quantity": 2})

    response = auth_client.post(
        "/checkout",
        data={"address": "12 Park Street, Pune 411001"},
        follow_redirects=True,
    )
    body = response.get_data(as_text=True)

    assert "Order confirmed" in body
    assert "Aurora Wireless Headphones × 2" in body
    assert "12 Park Street, Pune 411001" in body
    assert "₹9,998" in body
    assert "Your cart is empty" in auth_client.get("/cart").get_data(as_text=True)


def test_order_history_lists_placed_orders(auth_client):
    auth_client.post("/cart/add/1", data={"quantity": 1})
    auth_client.post("/checkout", data={"address": "12 Park Street"})

    body = auth_client.get("/orders").get_data(as_text=True)

    assert "Order #1" in body
    assert "1 item" in body


def test_order_history_is_empty_for_new_user(auth_client):
    assert "No orders yet" in auth_client.get("/orders").get_data(as_text=True)


def test_other_users_orders_are_not_visible(client, auth_client):
    auth_client.post("/cart/add/1", data={"quantity": 1})
    auth_client.post("/checkout", data={"address": "12 Park Street"})

    client.post(
        "/register",
        data={
            "full_name": "Nosy Neighbour",
            "email": "nosy@example.com",
            "phone": "",
            "password": "supersecret",
        },
    )

    assert client.get("/orders/1").status_code == 404
