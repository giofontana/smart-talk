# ── Build stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ── Runtime stage ────────────────────────────────────────────────────────────
FROM python:3.12-slim

# Install /install tree from builder
COPY --from=builder /install /usr/local

# Non-root user (uid 1001)
RUN useradd --uid 1001 --no-create-home --shell /sbin/nologin appuser

WORKDIR /app

COPY app/ ./app/

# Default config location; can be overridden via SMART_TALK_CONFIG env var
ENV SMART_TALK_CONFIG=/app/config.yaml

USER 1001

EXPOSE 8765

ENTRYPOINT ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8765"]
