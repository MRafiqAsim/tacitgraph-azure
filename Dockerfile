FROM python:3.11-slim

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Python deps — install in two stages for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# spaCy models (small models for cloud — LLM mode doesn't need trf)
RUN python -m spacy download en_core_web_sm && \
    python -m spacy download nl_core_news_sm

# App code + config
COPY src/ src/
COPY config/ config/
# Create empty data dirs (cloud mode doesn't need local files,
# but app checks for gold_path existence when cosmos is not set)
RUN mkdir -p data/gold_llm data/silver_llm

# Gradio port (App Service uses 8000 by default, configurable via WEBSITES_PORT)
EXPOSE 8000

# Launch in LLM mode — all data from Cosmos Gremlin + Azure AI Search
CMD ["python", "-m", "src.app", "--mode", "llm", "--port", "8000"]
