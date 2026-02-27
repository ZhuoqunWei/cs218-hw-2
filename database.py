import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.db")


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id    TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            item_id     TEXT NOT NULL,
            quantity    INTEGER NOT NULL,
            status      TEXT NOT NULL DEFAULT 'created',
            created_at  TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS ledger (
            ledger_id   TEXT PRIMARY KEY,
            order_id    TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            amount      INTEGER NOT NULL,
            created_at  TEXT NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(order_id)
        );

        CREATE TABLE IF NOT EXISTS idempotency_records (
            idempotency_key TEXT PRIMARY KEY,
            request_hash    TEXT NOT NULL,
            response_body   TEXT NOT NULL,
            status_code     INTEGER NOT NULL,
            created_at      TEXT NOT NULL
        );
    """)
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized.")
