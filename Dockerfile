# Build stage
FROM python:3.12 AS builder

# Add build metadata
LABEL maintainer="CopterSpotter Team"
LABEL version="26.3.1"
LABEL code_date="20260208"
LABEL description="Feed CopterSpotter Service"

# Set build arguments
ARG DEBIAN_FRONTEND=noninteractive

# Set working directory
WORKDIR /build

# Set Python environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install build dependencies
RUN apt-get update
RUN apt-get install -y --no-install-recommends gcc python3-dev
RUN    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-deps --wheel-dir /build/wheels -r requirements.txt

# Runtime stage
FROM python:3.12-slim

ARG VERSION=26.3.1

# Add runtime metadata
LABEL maintainer="CopterSpotter Team"
LABEL version="${VERSION}"
LABEL code_date="20260208"
LABEL description="Feed CopterSpotter Service"

# Set working directory
WORKDIR /app

# Create non-root user
RUN which groupadd
RUN groupadd -r copterspotter
RUN useradd -r -g copterspotter -s /bin/false copterspotter
RUN mkdir -p /app/logs
RUN chown -R copterspotter:copterspotter /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    iputils-ping \
    ca-certificates \
    && \
    rm -rf /var/lib/apt/lists/*

# Copy wheels and install dependencies
COPY --from=builder /build/wheels /wheels
COPY --from=builder /build/requirements.txt .
RUN pip install --upgrade --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Copy application code and entrypoint
COPY --chown=copterspotter:copterspotter fcs.py .
COPY --chown=copterspotter:copterspotter icao_heli_types.py .
COPY --chown=copterspotter:copterspotter config/ ./config/
COPY --chown=copterspotter:copterspotter docker-entrypoint.sh .
RUN chmod +x docker-entrypoint.sh

# Create necessary directories with proper permissions
RUN mkdir -p /app/data && \
    chown -R copterspotter:copterspotter /app/data

# Set environment variables (service version aligns with app version for OTEL)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC \
    OTEL_SERVICE_VERSION=${VERSION}

# Expose port
EXPOSE 8999

# Switch to non-root user
USER copterspotter

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8999/health || exit 1

# Entrypoint wires GRAFANA_OTLP_* to OTEL headers, then runs opentelemetry-instrument
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["python3", "fcs.py", "-i", "15", "-w", "-v"]
