import uuid
import hashlib
import json
import logging
from datetime import datetime, timezone

from flask import Flask, request, jsonify, g

from database import get_db, init_db

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Middleware – attach X-Request-Id to every request / response
# ---------------------------------------------------------------------------
@app.before_request
def attach_request_id():
    g.request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))


@app.after_request
def add_request_id_header(response):
    response.headers["X-Request-Id"] = g.request_id
    return response


# ---------------------------------------------------------------------------
# Startup – ensure tables exist
# ---------------------------------------------------------------------------
with app.app_context():
    init_db()


# ---------------------------------------------------------------------------
# POST /orders
# ---------------------------------------------------------------------------
@app.route("/orders", methods=["POST"])
def create_order():
    # 1. Require Idempotency-Key header
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return jsonify({"error": "Missing Idempotency-Key header"}), 400

    # 2. Hash the request body
    raw_body = request.get_data(as_text=True)
    request_hash = hashlib.sha256(raw_body.encode()).hexdigest()

    # 3. Check idempotency_records
    db = get_db()
    try:
        row = db.execute(
            "SELECT request_hash, response_body, status_code FROM idempotency_records WHERE idempotency_key = ?",
            (idempotency_key,),
        ).fetchone()

        if row:
            if row["request_hash"] == request_hash:
                # Idempotent replay – return the stored response
                log.info("Idempotent replay for key=%s", idempotency_key)
                return (
                    json.loads(row["response_body"]),
                    row["status_code"],
                    {"Content-Type": "application/json"},
                )
            else:
                # Same key, different payload → conflict
                return jsonify({"error": "Idempotency-Key already used with a different request payload"}), 409

        # 4. Parse body & create order + ledger in one transaction
        data = json.loads(raw_body)
        customer_id = data["customer_id"]
        item_id = data["item_id"]
        quantity = int(data["quantity"])

        order_id = str(uuid.uuid4())
        ledger_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        response_body = {
            "order_id": order_id,
            "customer_id": customer_id,
            "item_id": item_id,
            "quantity": quantity,
            "status": "created",
            "created_at": now,
        }
        status_code = 201

        db.execute("BEGIN")
        db.execute(
            "INSERT INTO orders (order_id, customer_id, item_id, quantity, status, created_at) VALUES (?, ?, ?, ?, 'created', ?)",
            (order_id, customer_id, item_id, quantity, now),
        )
        db.execute(
            "INSERT INTO ledger (ledger_id, order_id, customer_id, amount, created_at) VALUES (?, ?, ?, ?, ?)",
            (ledger_id, order_id, customer_id, quantity, now),
        )
        db.execute(
            "INSERT INTO idempotency_records (idempotency_key, request_hash, response_body, status_code, created_at) VALUES (?, ?, ?, ?, ?)",
            (idempotency_key, request_hash, json.dumps(response_body), status_code, now),
        )
        db.commit()

        log.info("Order created order_id=%s key=%s", order_id, idempotency_key)

        # 5. Debug hook – simulate failure after commit
        if request.headers.get("X-Debug-Fail-After-Commit", "").lower() == "true":
            log.warning("Simulated failure after commit for key=%s", idempotency_key)
            return jsonify({"error": "Simulated failure after commit"}), 500

        # 6. Return success
        return jsonify(response_body), status_code

    except Exception as exc:
        db.rollback()
        log.exception("Error creating order")
        return jsonify({"error": str(exc)}), 500
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GET /orders/<order_id>
# ---------------------------------------------------------------------------
@app.route("/orders/<order_id>", methods=["GET"])
def get_order(order_id):
    db = get_db()
    try:
        row = db.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
        if not row:
            return jsonify({"error": "Order not found"}), 404
        return jsonify(dict(row)), 200
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
