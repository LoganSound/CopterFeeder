# Build stage
FROM python:3.12-slim AS builder

# Add build metadata
LABEL maintainer="CopterSpotter Team"
LABEL version="20250201-01"
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
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        gcc \
        python3-dev \
        && \
    rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip wheel --no-deps --wheel-dir /build/wheels -r requirements.txt

# Runtime stage
FROM python:3.12-slim

# Add runtime metadata
LABEL maintainer="CopterSpotter Team"
LABEL version="20250201-01"
LABEL description="Feed CopterSpotter Service"

# Set working directory
WORKDIR /app

# Create non-root user
RUN groupadd -r copterspotter && \
    useradd -r -g copterspotter -s /bin/false copterspotter && \
    mkdir -p /app/logs && \
    chown -R copterspotter:copterspotter /app

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
RUN pip install --no-cache-dir /wheels/* && \
    rm -rf /wheels

# Copy application code
COPY --chown=copterspotter:copterspotter feed_copterspotter.py .
COPY --chown=copterspotter:copterspotter config/ ./config/

# Create necessary directories with proper permissions
RUN mkdir -p /app/data && \
    chown -R copterspotter:copterspotter /app/data

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=UTC

# Expose port
EXPOSE 8999

# Switch to non-root user
USER copterspotter

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD curl -f http://localhost:8999/health || exit 1

# Set default command
CMD ["python3", "fcs.py", "-i", "15", "-w", "-v"]
