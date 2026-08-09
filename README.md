# My-online-shopping-store
A full-stack E-Commerce web application built using Python, Flask, MySQL, HTML, CSS, and Bootstrap. This project includes user authentication, product management, shopping cart, order processing, and a responsive user interface with a secure backend and database integration

## Configuration

All secrets are read from the environment (see `.env.example`); nothing is
hardcoded in the source. Required variables:

| Variable | Purpose |
| --- | --- |
| `DB_HOST` / `DB_USER` / `DB_PASSWORD` / `DB_NAME` / `DB_PORT` | MySQL connection |
| `FLASK_SECRET_KEY` | Session signing key, app refuses to start without it |
| `RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET` | Razorpay credentials |
| `EMAIL` / `EMAIL_PASSWORD` | SMTP account used to send password reset OTPs |
| `ADMIN_EMAILS` | Comma separated e-mails allowed to use the admin/product routes |
| `SESSION_COOKIE_SECURE` | `1` by default, set to `0` for local plain-HTTP development |
| `FLASK_DEBUG` | `1` enables the Werkzeug debugger, never set it in production |
