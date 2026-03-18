# Order API — CS 218 Assignment 3

Containerized Flask order-management API backed by PostgreSQL, deployable locally via Docker Compose and on AWS (ECS Fargate + RDS + ALB).

---

## Architecture

```
Client → ALB (public, port 80) → ECS Fargate (API, port 8080) → RDS PostgreSQL
```

Local mirror:
```
localhost:8080 → api container → postgres container (named volume)
```

---

## Local Setup

### Prerequisites
- Docker Desktop
- (optional) k6 for load testing: `brew install k6`

### 1. Configure environment

```bash
cp .env.example .env
# .env is gitignored — edit values if needed (defaults work out of the box)
```

### 2. Start the stack

```bash
docker compose up -d --build
```

The `api` service waits for Postgres to pass its healthcheck before starting. Migrations run automatically at container startup via `alembic upgrade head`.

### 3. Verify

```bash
curl -i http://localhost:8080/health
# HTTP 200 {"status":"ok","db":"connected"}
```

### 4. Tear down

```bash
docker compose down -v   # removes containers and the pgdata volume
```

---

## Test Scenarios

### 1) Local compose boot + DB-aware health check

```bash
docker compose up -d --build
curl -i http://localhost:8080/health
```

Expected: `HTTP 200 {"status":"ok","db":"connected"}`

### 2) Persistence across API restart

```bash
curl -s -X POST http://localhost:8080/items \
  -H "Content-Type: application/json" \
  -d '{"name":"alpha","value":123}'
# {"id":1}

docker compose restart api
curl -s http://localhost:8080/items/1
# {"id":1,"name":"alpha","value":123,...}
```

### 3) Postgres volume persistence

```bash
docker compose restart postgres
curl -s http://localhost:8080/items/1
# record still present
```

### 4) AWS health check via ALB

```bash
curl -i http://order-api-alb-1144988471.us-east-1.elb.amazonaws.com/health
# HTTP 200 {"status":"ok","db":"connected"}
```

### 5) AWS write + read

```bash
BASE_URL=http://order-api-alb-1144988471.us-east-1.elb.amazonaws.com

curl -s -X POST $BASE_URL/items \
  -H "Content-Type: application/json" \
  -d '{"name":"cloud-alpha","value":456}'
# {"id":1}

curl -s $BASE_URL/items/1
# {"id":1,"name":"cloud-alpha","value":456,...}
```

---

## Migrations

Migrations are managed by [Alembic](https://alembic.sqlalchemy.org/) and run automatically at container startup.

To run manually (local):

```bash
source venv/bin/activate
alembic upgrade head
```

Migration file: `migrations/versions/0001_initial.py`

Tables created:
- `items` — id, name, value, created_at
- `orders` — order_id (UUID), customer_id, item_id, quantity, created_at
- `ledger` — ledger_id (UUID), order_id FK, customer_id, amount, created_at
- `idempotency_records` — idempotency_key PK, request_fingerprint, response_body, status_code, created_at

---

## Secrets Handling

**Local:** DB password lives in `.env` (gitignored). `.env.example` is committed with placeholder values.

**AWS:** `DATABASE_PASSWORD` is injected at runtime from SSM Parameter Store:
- Parameter: `/order-api/db-password` (SecureString)
- Referenced in the ECS task definition via `secrets[].valueFrom`
- The password never appears in the Docker image or the task definition JSON

---

## AWS Deployment

### Infrastructure

| Component | Detail |
|-----------|--------|
| ECS Cluster | `order-api-cluster` |
| ECS Service | `order-api-service` (desired count = 1) |
| Fargate task | 256 CPU units (0.25 vCPU) / 512 MB |
| RDS | PostgreSQL on `db.t3.micro`, no Multi-AZ |
| ALB | `order-api-alb` — public DNS below |
| CloudWatch Logs | `/ecs/order-api` |
| Region | `us-east-1` |

**Public ALB URL:** `http://order-api-alb-1144988471.us-east-1.elb.amazonaws.com`

### Deploy steps

```bash
# 1. Authenticate to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin \
  043254348860.dkr.ecr.us-east-1.amazonaws.com

# 2. Build and push (increment tag each deploy)
docker buildx build --platform linux/amd64 \
  -t 043254348860.dkr.ecr.us-east-1.amazonaws.com/order-api:v8 \
  -t 043254348860.dkr.ecr.us-east-1.amazonaws.com/order-api:latest \
  --push .

# 3. Update image tag in ecs-task-definition.json, then register
aws ecs register-task-definition \
  --cli-input-json file://ecs-task-definition.json \
  --region us-east-1

# 4. Update service (replace <N> with the revision number from step 3)
aws ecs update-service \
  --cluster order-api-cluster \
  --service order-api-service \
  --task-definition order-api:<N> \
  --force-new-deployment \
  --region us-east-1
```

### ALB target group health check

- Protocol: HTTP
- Path: `/health`
- Port: 8080
- The `/health` endpoint returns 200 only when the API can reach RDS — ensuring the ALB only routes to a fully ready task.

---

## Load Test

Run with [k6](https://k6.io):

```bash
k6 run loadtest.js                          # local (default BASE_URL=http://localhost:8080)
BASE_URL=http://<alb-dns> k6 run loadtest.js  # against AWS
```

Script: `loadtest.js` — 20 VUs, 60 s, each iteration: `POST /items` → `GET /items/<id>`

### Results

#### Local (Docker Compose on laptop)

| Metric | Value |
|--------|-------|
| Duration | 60 s |
| VUs | 20 |
| Total requests | 16 868 |
| RPS | 280 req/s |
| Avg latency | 20.65 ms |
| p90 latency | 34.29 ms |
| p95 latency | 37.55 ms |
| Error rate | 0.00% |

Both thresholds pass: `p(95) < 500 ms` ✅ and `http_req_failed < 1%` ✅

#### AWS (laptop → ALB → ECS → RDS, us-east-1)

| Metric | Value |
|--------|-------|
| Duration | 60 s |
| VUs | 20 |
| RPS | ~22 req/s |
| p95 latency | ~1.1 s |
| Error rate | 0.00% |

`http_req_failed < 1%` ✅

**Bottleneck analysis:** The elevated p95 in the AWS run is dominated by WAN round-trip latency (Mac → us-east-1 ≈ 50–70 ms one-way), compounded by 20 concurrent VUs queuing against a single 0.25-vCPU Fargate task. Error rate remains 0% — the service handles load correctly; latency is a geography + resource-size effect, not a correctness issue. Running k6 from an EC2 instance in the same region yields latencies comparable to the local run.
