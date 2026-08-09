from config import cursor, db


def fetch_all(sql, params=()):
    cursor.execute(sql, params)
    return cursor.fetchall()


def fetch_one(sql, params=()):
    cursor.execute(sql, params)
    return cursor.fetchone()


def fetch_value(sql, params=(), default=None):
    row = fetch_one(sql, params)

    if row is None or row[0] is None:
        return default

    return row[0]


def execute(sql, params=()):
    cursor.execute(sql, params)
    db.commit()
