import mysql.connector

db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="annu2004",
    database="ecommerce_db"
)

cursor = db.cursor(buffered=True)


RAZORPAY_KEY_ID = "rzp_test_TLJTjoSTwdiNSO"
RAZORPAY_KEY_SECRET = "UAUODs7BOqMVjUE4Q6kgTyKB"

EMAIL = "anmol649kumar@gmail.com"
EMAIL_PASSWORD = "anmol.2004"