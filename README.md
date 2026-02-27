# Order Service API — CS-218 Assignment 2

Idempotent Order API built with Flask + SQLite.

## Local Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

## EC2 Deployment (Amazon Linux 2, t2.micro)

```bash
sudo yum update -y
sudo yum install python3 python3-pip git -y
git clone <REPO_URL> && cd hw2-Zhuoqun-Wei
pip3 install -r requirements.txt
gunicorn -w 1 -b 0.0.0.0:5000 app:app --daemon
```

Security Group: allow TCP **5000** and **22** inbound.

## Verification (replace `<BASE_URL>`)

### Step 1 — Create an order (expect 201)
```bash
curl -X POST <BASE_URL>/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-abc-123" \
  -d '{"customer_id":"cust-1","item_id":"item-42","quantity":2}'
```

### Step 2 — Retry same key + payload (expect same 201 response)
```bash
curl -X POST <BASE_URL>/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-abc-123" \
  -d '{"customer_id":"cust-1","item_id":"item-42","quantity":2}'
```

### Step 3 — Same key, different payload (expect 409)
```bash
curl -X POST <BASE_URL>/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-abc-123" \
  -d '{"customer_id":"cust-1","item_id":"item-99","quantity":5}'
```

### Step 4 — Simulated failure after commit (expect 500)
```bash
curl -X POST <BASE_URL>/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-fail-456" \
  -H "X-Debug-Fail-After-Commit: true" \
  -d '{"customer_id":"cust-2","item_id":"item-7","quantity":1}'
```

### Step 5 — Retry after failure (expect 201 with same order)
```bash
curl -X POST <BASE_URL>/orders \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: order-fail-456" \
  -d '{"customer_id":"cust-2","item_id":"item-7","quantity":1}'
```

### Step 6 — GET order by ID (use order_id from step 1)
```bash
curl <BASE_URL>/orders/<ORDER_ID>
```
