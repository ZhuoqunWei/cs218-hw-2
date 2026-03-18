# --- build stage ---
FROM python:3.13-slim AS builder
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- runtime stage ---
FROM python:3.13-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY . .
RUN adduser --disabled-password --no-create-home app && \
    mkdir -p /run/gunicorn && chown app /run/gunicorn
USER app
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1
CMD ["sh", "-c", "alembic upgrade head && gunicorn -b 0.0.0.0:8080 --worker-tmp-dir /run/gunicorn app:app"]
