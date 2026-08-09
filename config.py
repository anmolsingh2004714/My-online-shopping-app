import logging
import os

import mysql.connector

logger = logging.getLogger(__name__)

try:
    db = mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "ecommerce_db"),
        port=int(os.getenv("DB_PORT", "3306"))
    )
except mysql.connector.Error as error:
    raise RuntimeError(
        "Could not connect to the MySQL database. Check DB_HOST, DB_USER, "
        "DB_PASSWORD, DB_NAME and DB_PORT."
    ) from error

cursor = db.cursor(buffered=True)

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

EMAIL = os.getenv("EMAIL")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

if not (RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET):
    logger.warning(
        "RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET are not set; "
        "payment routes will be unavailable."
    )

if not (EMAIL and EMAIL_PASSWORD):
    logger.warning(
        "EMAIL / EMAIL_PASSWORD are not set; "
        "password reset emails cannot be sent."
    )
