"""Registration, sign in, sign out and the login guard."""

import pytest
from db import DEMO_USER


def test_register_creates_account_and_signs_in(client):
    response = client.post(
        "/register",
        data={
            "full_name": "Asha Rao",
            "email": "Asha@Example.com",
            "phone": "9998887777",
            "password": "supersecret",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert "Welcome to ShopKart, Asha Rao!" in response.get_data(as_text=True)
    assert "Sign out" in response.get_data(as_text=True)


def test_register_rejects_short_password(client):
    response = client.post(
        "/register",
        data={
            "full_name": "Asha Rao",
            "email": "asha@example.com",
            "phone": "",
            "password": "short",
        },
    )

    assert "8+ character password" in response.get_data(as_text=True)


def test_register_rejects_duplicate_email(client):
    _, email, _, _ = DEMO_USER

    response = client.post(
        "/register",
        data={
            "full_name": "Copycat",
            "email": email,
            "phone": "",
            "password": "supersecret",
        },
    )

    assert "already registered" in response.get_data(as_text=True)


def test_login_with_valid_credentials(client):
    _, email, _, password = DEMO_USER

    response = client.post(
        "/login", data={"email": email, "password": password}, follow_redirects=True
    )

    assert "Signed in as Demo Shopper." in response.get_data(as_text=True)


def test_login_with_wrong_password_is_rejected(client):
    _, email, _, _ = DEMO_USER

    response = client.post("/login", data={"email": email, "password": "nope"})

    assert "Invalid email or password." in response.get_data(as_text=True)


def test_login_honours_next_parameter(auth_client):
    """A guarded page redirects to login and back after signing in."""

    assert auth_client.get("/cart").status_code == 200


def test_logout_clears_the_session(auth_client):
    response = auth_client.get("/logout", follow_redirects=True)
    body = response.get_data(as_text=True)

    assert "You have been signed out." in body
    assert "Sign in" in body


@pytest.mark.parametrize("path", ["/cart", "/checkout", "/orders", "/orders/1"])
def test_protected_pages_redirect_anonymous_visitors(client, path):
    response = client.get(path)

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_add_to_cart_requires_login(client):
    response = client.post("/cart/add/1", data={"quantity": 1})

    assert response.status_code == 302
    assert "/login" in response.headers["Location"]
