#!/bin/sh
# Wire GRAFANA_OTLP_* env vars into OTEL_EXPORTER_OTLP_* for Grafana Cloud OTLP auth.
# When GRAFANA_OTLP_USERNAME and GRAFANA_OTLP_API_KEY are set, constructs
# OTEL_EXPORTER_OTLP_HEADERS with Basic auth. When GRAFANA_OTLP_ENDPOINT is set,
# uses it for OTEL_EXPORTER_OTLP_ENDPOINT.
# Set OTEL Resource attribute feeder_id from FEEDER_ID when present.

if [ -n "$FEEDER_ID" ]; then
    if [ -n "$OTEL_RESOURCE_ATTRIBUTES" ]; then
        export OTEL_RESOURCE_ATTRIBUTES="${OTEL_RESOURCE_ATTRIBUTES},feeder_id=${FEEDER_ID}"
    else
        export OTEL_RESOURCE_ATTRIBUTES="feeder_id=${FEEDER_ID}"
    fi
fi

if [ -n "$GRAFANA_OTLP_USERNAME" ] && [ -n "$GRAFANA_OTLP_API_KEY" ]; then
    creds=$(printf '%s:%s' "$GRAFANA_OTLP_USERNAME" "$GRAFANA_OTLP_API_KEY")
    export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic $(echo -n "$creds" | base64 -w 0 2>/dev/null || echo -n "$creds" | base64 | tr -d '\n')"
fi

if [ -n "$GRAFANA_OTLP_ENDPOINT" ]; then
    export OTEL_EXPORTER_OTLP_ENDPOINT="$GRAFANA_OTLP_ENDPOINT"
fi

# Grafana Cloud OTLP uses HTTP (not gRPC); required for otlphttp endpoint
if [ -n "$GRAFANA_OTLP_USERNAME" ] || [ -n "$GRAFANA_OTLP_ENDPOINT" ]; then
    export OTEL_EXPORTER_OTLP_PROTOCOL="${OTEL_EXPORTER_OTLP_PROTOCOL:-http/protobuf}"
fi

# Disable OTLP exporters when no endpoint is configured to avoid connection errors to localhost:4317
if [ -z "$OTEL_EXPORTER_OTLP_ENDPOINT" ]; then
    export OTEL_TRACES_EXPORTER=none
    export OTEL_METRICS_EXPORTER=none
    export OTEL_LOGS_EXPORTER=none
fi

exec opentelemetry-instrument "$@"
