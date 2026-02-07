#!/bin/sh
# Wire GRAFANA_OTLP_* env vars into OTEL_EXPORTER_OTLP_* for Grafana Cloud OTLP auth.
# When GRAFANA_OTLP_USERNAME and GRAFANA_OTLP_API_KEY are set, constructs
# OTEL_EXPORTER_OTLP_HEADERS with Basic auth. When GRAFANA_OTLP_ENDPOINT is set,
# uses it for OTEL_EXPORTER_OTLP_ENDPOINT.

if [ -n "$GRAFANA_OTLP_USERNAME" ] && [ -n "$GRAFANA_OTLP_API_KEY" ]; then
    creds=$(printf '%s:%s' "$GRAFANA_OTLP_USERNAME" "$GRAFANA_OTLP_API_KEY")
    export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Basic $(echo -n "$creds" | base64 -w 0 2>/dev/null || echo -n "$creds" | base64 | tr -d '\n')"
fi

if [ -n "$GRAFANA_OTLP_ENDPOINT" ]; then
    export OTEL_EXPORTER_OTLP_ENDPOINT="$GRAFANA_OTLP_ENDPOINT"
fi

exec opentelemetry-instrument "$@"
