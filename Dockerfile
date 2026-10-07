# TacitGraph chat app for Azure App Service.
# Retrieval runs against Cosmos DB Gremlin + Azure AI Search, so the image only
# needs the `azure` extra — no local NLP models (spaCy / torch) are installed.

FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.9 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    TACITGRAPH_HOME=/app \
    GRADIO_ANALYTICS_ENABLED=False \
    HF_HUB_DISABLE_TELEMETRY=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first, so code changes don't invalidate this layer
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra azure

COPY README.md LICENSE NOTICE ./
COPY config/ config/
COPY src/ src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --extra azure

# The app expects these paths to exist even when data comes from Azure services
RUN mkdir -p data/gold_llm data/silver_llm \
    && useradd --create-home --uid 1000 app \
    && chown -R app:app /app
USER app

# App Service routes traffic to port 8000 by default (override with WEBSITES_PORT)
EXPOSE 8000

CMD ["tacitgraph-app", "--mode", "llm", "--port", "8000"]
