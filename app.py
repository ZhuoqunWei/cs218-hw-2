import uuid
import hashlib
import json
from flask import Flask, request, jsonify
from database import get_db, check_db

app = Flask(__name__)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    if check_db():
        return jsonify({"status": "ok", "db": "connected"}), 200
    return jsonify({"status": "error", "db": "disconnected"}), 503


# ---------------------------------------------------------------------------
# Items  (used by assignment test scenarios)
# ---------------------------------------------------------------------------

@app.route("/items", methods=["POST"])
def create_item():
    data = request.get_json(silent=True) or {}
    name = data.get("name")
    value = data.get("value")
    if name is None or value is None:
        return jsonify({"error": "name and value required"}), 400
    conn = get_db()
    try:
        with conn, conn.cursor() as cur:
            cur.execute(
                "INSERT INTO items (name, value) VALUES (%s, %s) RETURNING id",
                (name, value),
            )
            row = cur.fetchone()
        return jsonify({"id": row["id"]}), 201
    finally:
        conn.close()


@app.route("/items/<int:item_id>")
def get_item(item_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM items WHERE id = %s", (item_id,))
            row = cur.fetchone()
        if row is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(dict(row)), 200
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Orders
# ---------------------------------------------------------------------------

@app.route("/orders", methods=["POST"])
def create_order():
    data = request.get_json(silent=True) or {}
    customer_id = data.get("customer_id")
    item_id = data.get("item_id")
    quantity = data.get("quantity")
    amount = data.get("amount", 0)
    idempotency_key = request.headers.get("Idempotency-Key")

    if not all([customer_id, item_id, quantity]):
        return jsonify({"error": "customer_id, item_id, quantity required"}), 400

    conn = get_db()
    try:
        # Check idempotency
        if idempotency_key:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT response_body, status_code FROM idempotency_records WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
                existing = cur.fetchone()
            if existing:
                return app.response_class(
                    response=existing["response_body"],
                    status=existing["status_code"],
                    mimetype="application/json",
                )

        order_id = str(uuid.uuid4())
        ledger_id = str(uuid.uuid4())
        fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()

        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO orders (order_id, customer_id, item_id, quantity) VALUES (%s, %s, %s, %s)",
                    (order_id, customer_id, str(item_id), quantity),
                )
                cur.execute(
                    "INSERT INTO ledger (ledger_id, order_id, customer_id, amount) VALUES (%s, %s, %s, %s)",
                    (ledger_id, order_id, customer_id, amount),
                )
                if idempotency_key:
                    response_body = json.dumps({"order_id": order_id})
                    cur.execute(
                        "INSERT INTO idempotency_records (idempotency_key, request_fingerprint, response_body, status_code) VALUES (%s, %s, %s, %s)",
                        (idempotency_key, fingerprint, response_body, 201),
                    )

        return jsonify({"order_id": order_id}), 201
    finally:
        conn.close()


@app.route("/orders/<order_id>")
def get_order(order_id):
    conn = get_db()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
            row = cur.fetchone()
        if row is None:
            return jsonify({"error": "not found"}), 404
        return jsonify(dict(row)), 200
    finally:
        conn.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
