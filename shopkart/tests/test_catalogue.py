"""Home page, catalogue filters and product detail pages."""


def test_home_lists_featured_products(client):
    response = client.get("/")
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert "Top rated" in body
    assert "Kraft Mechanical Keyboard" in body


def test_products_page_lists_whole_catalogue(client):
    body = client.get("/products").get_data(as_text=True)

    assert "Aurora Wireless Headphones" in body
    assert "Trek Laptop Backpack" in body


def test_search_matches_name_and_description(client):
    body = client.get("/products?search=keyboard").get_data(as_text=True)

    assert "Kraft Mechanical Keyboard" in body
    assert "Trek Laptop Backpack" not in body


def test_search_without_matches_shows_empty_state(client):
    body = client.get("/products?search=zzzz").get_data(as_text=True)

    assert "No products matched your filters" in body


def test_category_filter_restricts_results(client):
    body = client.get("/products?category=Audio").get_data(as_text=True)

    assert "Aurora Wireless Headphones" in body
    assert "Pulse Gaming Mouse" not in body


def test_sort_by_price_ascending_orders_cheapest_first(client):
    body = client.get("/products?sort=price-asc").get_data(as_text=True)

    assert body.index("Pulse Gaming Mouse") < body.index("Kraft Mechanical Keyboard")


def test_sort_by_price_descending_orders_priciest_first(client):
    body = client.get("/products?sort=price-desc").get_data(as_text=True)

    assert body.index("Kraft Mechanical Keyboard") < body.index("Pulse Gaming Mouse")


def test_product_details_shows_price_and_related_items(client):
    body = client.get("/product/1").get_data(as_text=True)

    assert "Aurora Wireless Headphones" in body
    assert "₹4,999" in body
    assert "More in Audio" in body


def test_unknown_product_returns_404(client):
    response = client.get("/product/999")

    assert response.status_code == 404
    assert "404" in response.get_data(as_text=True)


def test_unknown_url_returns_404_page(client):
    assert client.get("/no-such-page").status_code == 404
