FROM python:3.12-slim AS builder

# Add build metadata
LABEL maintainer="CopterSpotter Team"
LABEL version="20250130-01"
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
    apt-get install -y --no-install-recommends gcc

COPY requirements.txt .

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

FROM python:3.12-slim

# Add runtime metadata
LABEL maintainer="CopterSpotter Team"
LABEL version="20250130-01"
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
    apt-get install -y --no-install-recommends curl iputils-ping


EXPOSE 8999

WORKDIR /app

COPY --from=builder /app/wheels /wheels
COPY --from=builder /app/requirements.txt .

RUN pip install --no-cache /wheels/*


COPY feed_copterspotter.py .
# 20241111 - removed copy of .env - see docker-compose "env_file:"" setting.
# COPY .env .


CMD ["python3", "feed_copterspotter.py", "-w", "-v"]
