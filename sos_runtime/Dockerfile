# SOS Runtime — production container.
# Single-stage build; the surface is small enough that staged builds
# would only save a few hundred KB. Multi-stage can land in a
# follow-up unit if image size becomes a real concern.

FROM python:3.12-slim

# Cloud Run picks the port via $PORT (default 8080). We listen on it
# directly without nginx — the platform terminates TLS.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080

WORKDIR /app

# System deps stay minimal — Firestore + Anthropic SDKs are pure Python.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy + install requirements first so layer caching works.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy the package. The tests directory is excluded via .dockerignore.
COPY . /app/sos_runtime

# Drop privileges. Cloud Run already runs as a non-root UID, but
# explicit beats implicit.
RUN useradd --create-home --uid 1001 sos
USER sos

# Health is publicly reachable; everything else requires bearer.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://localhost:8080/health',timeout=3).status==200 else 1)"

CMD ["sh", "-c", "uvicorn sos_runtime.main:app --host 0.0.0.0 --port ${PORT}"]
