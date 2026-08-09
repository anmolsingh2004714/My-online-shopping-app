import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from db import DEMO_USER  # noqa: E402  (needs the sys.path tweak above)

from app import create_app  # noqa: E402


@pytest.fixture
def app(tmp_path):
    application = create_app(database=str(tmp_path / "test.sqlite3"))
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Client signed in as the seeded demo user."""

    _, email, _, password = DEMO_USER
    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 302
    return client
