FROM python:3.12-slim

# OS deps kept minimal — fpdf2 is pure Python; no pango/cairo needed.
# curl only used by HEALTHCHECK below.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first for better cache behaviour.
COPY pyproject.toml ./
RUN pip install --no-cache-dir -e .

# Copy source last.
COPY main.py ./
COPY src/ ./src/

# Persist SQLite + artifacts on a named volume mounted at /app/data.
# Declaring an env var keeps the artifact base consistent whether running in
# or out of Docker.
ENV ARTIFACTS_BASE=/app/data/artifacts
RUN mkdir -p /app/data /app/data/artifacts

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
