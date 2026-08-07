import os
import mysql.connector

db = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASSWORD", ""),
    database=os.getenv("DB_NAME", "ecommerce_db"),
    port=int(os.getenv("DB_PORT", "3306"))
)

cursor = db.cursor(buffered=True)

RAZORPAY_KEY_ID = os.getenv("rzp_test_TLJTjoSTwdiNSO")
RAZORPAY_KEY_SECRET = os.getenv("UAUODs7BOqMVjUE4Q6kgTyKB")

EMAIL = os.getenv("anmol640singh")
EMAIL_PASSWORD = os.getenv("anmol.2004")