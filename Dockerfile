FROM python:3.12-slim AS builder

#WORKDIR /usr/local/bin

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc

COPY requirements.txt .

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /app/wheels -r requirements.txt

FROM python:3.12-slim

# adding for debug purposes
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
