# ShopKart — responsive Flask + Tailwind storefront

A self-contained e-commerce demo built with Python (Flask), Jinja templates,
Tailwind CSS and vanilla JavaScript. It uses SQLite, so it runs anywhere with
no database server, credentials or API keys.

## Features

- Landing page with hero, category chips and top-rated products
- Catalogue with search, category filter and price/name/rating sorting
- Product detail page with quantity picker and related products
- Session based auth (register / sign in / sign out), passwords hashed with Werkzeug
- Cart with quantity +/-, remove, subtotal, free-shipping threshold and badge count
- Checkout that writes an order and clears the cart, plus order history and detail pages
- Responsive from 320px upwards: mobile drawer nav, fluid grids, sticky summary on desktop

## Run it

```bash
cd shopkart
python -m venv venv && source venv/bin/activate    # Windows: venv\Scripts\activate
pip install -r requirements.txt
flask --app app run --debug
```

Then open http://127.0.0.1:5000.

The schema and demo catalogue are created on first start in
`instance/shopkart.sqlite3`. Set `DATABASE` to use another path and `SECRET_KEY`
in production.

Demo account: `demo@shopkart.test` / `demo1234`.

## Tests

```bash
python -m pytest tests -q
```

Each test runs against a throwaway SQLite file, so no fixtures leak between tests.

## Layout

```
shopkart/
├── app.py            # app factory, routes, cart maths
├── db.py             # schema, connection helpers, demo seed data
├── templates/        # Jinja templates (Tailwind utility classes)
├── static/           # small custom CSS and product photos (see static/img/CREDITS.md)
└── tests/            # pytest suite covering auth, catalogue, cart, checkout
```

Tailwind is loaded from the CDN to keep the project dependency-free; for
production, install `tailwindcss` and build a purged stylesheet instead.
