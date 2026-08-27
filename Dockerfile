# Multi-Stage Production Dockerfile for NexusRAG Enterprise v0.2.0
FROM python:3.10-slim AS builder

WORKDIR /app

# Install system dependencies including Rust toolchain for native extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final Minimal Runtime Stage
FROM python:3.10-slim

WORKDIR /app

# Copy installed python wheels from builder
COPY --from=builder /root/.local /root/.local
ENV PATH="/root/.local/bin:${PATH}"
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Copy application source code
COPY . .

# Create persistent data directory
RUN mkdir -p /app/data

EXPOSE 8000

# Healthcheck probe against SQLite database & API
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]
