<div align="center">

# TacitGraph · Azure

### From PST to a knowledge graph you can chat with — at enterprise scale on Azure

**An end-to-end RAG pipeline** on Azure: ingestion, knowledge-graph construction and graph-aware retrieval as managed cloud services.

*The cloud deployment of [TacitGraph](https://github.com/MRafiqAsim/tacitgraph): Synapse for processing, Cosmos DB for the knowledge graph, AI Search for retrieval and App Service for the chat UI.*

[![CI](https://github.com/MRafiqAsim/tacitgraph-azure/actions/workflows/ci.yml/badge.svg)](https://github.com/MRafiqAsim/tacitgraph-azure/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Buy me a coffee](https://img.shields.io/badge/Buy%20me%20a%20coffee-€5-ffdd00?logo=paypal&logoColor=white)](https://paypal.me/mrafiq89/5EUR)

</div>

---

## Introduction

TacitGraph builds an end-to-end pipeline that transforms unstructured expert knowledge — primarily email archives (PST files) and attached documents — into a queryable knowledge graph with multiple retrieval strategies.

The pipeline follows a Bronze/Silver/Gold medallion architecture:

- **Bronze**: Raw extraction from PST archives — emails, attachments, thread grouping, language detection
- **Silver**: NLP processing — work / personal classification, cleaning, chunking, entity and relationship extraction (EN/NL, translated to English), summarisation
- **Gold**: Knowledge graph construction, community detection (Leiden), path indexing, embedding generation

Five retrieval strategies are available through a Gradio web interface:

- **Vector Search** — Hybrid keyword (BM25) + dual-vector search (text + summary embeddings) with semantic reranking in Azure AI Search
- **PathRAG** — Multi-hop entity path reasoning via knowledge graph DFS
- **GraphRAG** — Community-based context retrieval (local 1-hop + global map-reduce)
- **Hybrid** — Weighted fusion: Vector (0.3) + PathRAG (0.4) + GraphRAG (0.3)
- **ReAct** — Autonomous agent with tool-based reasoning and cross-validation

This repository targets **Azure cloud deployment** using Synapse Analytics, ADLS Gen2, Cosmos DB, AI Search and App Service.

## Which edition do you need?

TacitGraph comes in two editions that share the same pipeline and retrieval strategies:

| | [**TacitGraph**](https://github.com/MRafiqAsim/tacitgraph) — local | [**TacitGraph · Azure**](https://github.com/MRafiqAsim/tacitgraph-azure) — cloud |
|---|---|---|
| Runs on | A laptop or a single server, natively or in Docker | Azure managed services |
| Processing | Command-line tools | Synapse Analytics (Spark pool); PST extraction runs locally |
| Data layers | JSON files on disk | ADLS Gen2 |
| Knowledge graph | NetworkX (GraphML / JSON files) | Cosmos DB (Gremlin API), plus NetworkX in memory for PathRAG |
| Search | In-memory BM25 + exact vector search, fused with RRF | Azure AI Search: HNSW vectors + BM25 + semantic ranker |
| Chat model | Ollama (Llama 3.1 by default), Azure OpenAI or OpenAI | Azure OpenAI (GPT-4o) |
| Embeddings | bge-m3 locally, or OpenAI | Azure OpenAI (text-embedding-3-small) |
| Chat UI | Gradio on your machine | Gradio on App Service |
| Best for | Personal and team archives, offline or private use, trying it out | Organisation-wide archives and many concurrent users |
| Cost | Your own hardware | Azure consumption |

> **You are in the Azure edition.** Running on a laptop or your own server, with local models or without Azure? Use **[tacitgraph](https://github.com/MRafiqAsim/tacitgraph)**.

### High Level Architecture

![High Level Architecture](diagrams/high_level_architecture.png)

### Data Flow

![Data Flow](diagrams/data_flow_diagram.png)

## Getting Started

### Software Dependencies

- Azure subscription with the following resources provisioned:
  - Azure OpenAI (GPT-4o + text-embedding-3-small deployments)
  - Azure AI Search
  - Azure Cosmos DB (Gremlin API)
  - Azure Data Lake Storage Gen2 (ADLS)
  - Azure Synapse Analytics (Apache Spark pool)
  - Azure Container Registry (ACR)
  - Azure App Service (Linux, B2+ plan — the graph is held in memory)
- Azure CLI installed and logged in
- Docker installed (for web app deployment)
- [uv](https://docs.astral.sh/uv/) and Python 3.11+ (for local Bronze extraction and development)

### Installation

```bash
git clone https://github.com/MRafiqAsim/tacitgraph-azure.git
cd tacitgraph-azure

uv sync --extra ingest --extra azure   # PST parsing + Azure SDKs
cp .env.template .env                  # fill in the Azure endpoints and keys
```

### Project Structure

```
src/tacitgraph/
├── bronze/            # PST extraction, document parsing, thread grouping
├── silver/            # Classification, KG extraction, chunking, summarization
├── gold/              # Graph builder, community detection, embeddings
├── pathrag/           # PathRAG algorithm (DFS + BFS flow pruning)
├── retrieval/         # Hybrid retriever, vector search, GraphRAG, ReAct
├── storage/           # ADLS adapter, Cosmos DB adapter
├── evaluation/        # RAGAS evaluator, comparative analysis
├── pipeline/          # CLI runners
├── app.py             # Gradio web UI
├── entity_registry.py # Entity catalog loader + alias expansion
├── prompt_loader.py   # Prompt management from config/prompts.json
└── settings.py        # Azure configuration management

config/
├── entity_config.json       # Entity types, aliases, relationship direction flips
├── prompts.json             # All LLM prompts (Bronze/Silver/Gold/Retrieval)
└── sensitivity_rules.yaml   # Work / personal classification rules

synapse/
└── notebooks/         # Azure Synapse pipeline notebooks

scripts/               # Stats, visualization, evaluation utilities
tests/                 # pytest suite
diagrams/              # Architecture diagrams
```

### Key Configuration

| File | Purpose |
|------|---------|
| `.env` | Azure credentials (never committed; see [`.env.template`](.env.template)) |
| `config/prompts.json` | All LLM prompts — edit to change behavior; `domain_context` describes your corpus |
| `config/entity_config.json` | Entity types, name aliases, relationship flips |
| `config/sensitivity_rules.yaml` | Work / personal classification rules |
| `Dockerfile` | Container build for Azure App Service |
| `pyproject.toml` / `uv.lock` | Python dependencies, managed with uv |

### Technology Stack

| Component | Technology |
|-----------|------------|
| LLM | Azure OpenAI GPT-4o |
| Embeddings | Azure OpenAI text-embedding-3-small |
| Search | Azure AI Search (BM25 + HNSW vectors + semantic reranker) |
| Graph DB | Azure Cosmos DB Gremlin |
| Storage | Azure Data Lake Storage Gen2 (ADLS) |
| Pipeline | Azure Synapse Analytics (Spark pool) |
| Community Detection | Leiden algorithm (multi-resolution) |
| PathRAG Graph | In-memory NetworkX (downloaded from ADLS — Gremlin too slow for DFS/BFS) |
| UI | Gradio (containerized on Azure App Service) |

## Build and Test

### 1. Extract Bronze Locally and Upload Data and Code to ADLS

> **Note:** Bronze ingestion (PST extraction) runs locally on Linux/WSL because it requires system libraries that cannot be installed on Synapse's managed Spark environment — specifically libpff/pypff (C library for PST parsing), pst-utils (readpst), antiword (legacy .doc parsing), and libreoffice (document format conversions). Bronze outputs are uploaded to ADLS for subsequent Silver and Gold processing on Synapse.

```bash
# Extract the Bronze layer locally
uv run tacitgraph-ingest --pst ./archive.pst --output ./data

# Upload Bronze data from local to ADLS
az storage blob upload-batch \
  --destination "<YOUR_CONTAINER>" \
  --source "./data/bronze" \
  --destination-path "bronze" \
  --account-name <YOUR_ADLS_ACCOUNT> \
  --account-key "<YOUR_ADLS_KEY>"

# Upload source code
az storage blob upload-batch \
  --destination "<YOUR_CONTAINER>" \
  --source "./src" \
  --destination-path "code/src" \
  --account-name <YOUR_ADLS_ACCOUNT> \
  --account-key "<YOUR_ADLS_KEY>" \
  --overwrite

# Upload config
az storage blob upload-batch \
  --destination "<YOUR_CONTAINER>" \
  --source "./config" \
  --destination-path "code/config" \
  --account-name <YOUR_ADLS_ACCOUNT> \
  --account-key "<YOUR_ADLS_KEY>" \
  --overwrite
```

### 2. Run Synapse Notebooks (in order)

| Step | Notebook | Description |
|------|----------|-------------|
| 1 | `01_bronze_ingestion.ipynb` | PST/document ingestion (source to Bronze) for files already on ADLS (optional) |
| 2 | `02_silver_processing.ipynb` | Thread processing (Bronze to Silver) |
| 3 | `03_a_gold_build_graph.ipynb` | Knowledge graph construction + ADLS upload |
| 4 | `03_b_gold_insert_to_cosmos_db.ipynb` | Upload nodes/edges to Cosmos DB Gremlin |
| 5 | `03_c_gold_detect_communities.ipynb` | Leiden community detection + LLM summaries |
| 6 | `03_d_gold_index_chunks.ipynb` | AI Search kg-chunks index (dual vector + semantic) |
| 7 | `03_e_gold_index_entities.ipynb` | AI Search kg-entities index (retrievable vectors) |
| 8 | `03_f_gold_index_communities.ipynb` | AI Search kg-communities index |
| 9 | `03_g_gold_index_thread_summaries.ipynb` | AI Search kg-thread-summaries index |
| 10 | `03_h_gold_index_attachment_summaries.ipynb` | AI Search kg-attachment-summaries index |
| 11 | `04_ragas_evaluation.ipynb` | RAGAS evaluation (faithfulness, relevancy, precision, recall, correctness) |
| 12 | `05_pipeline_stats.ipynb` | Layer statistics and entity / relationship reports |

### AI Search Indexes

| Index | Purpose | Key Fields |
|-------|---------|------------|
| `kg-chunks` | Email/attachment chunks | text_english, summary, dual vectors, semantic config |
| `kg-entities` | Entity embeddings | name, node_type, entity_vector (retrievable) |
| `kg-communities` | Community summaries | summary, key_topics, level |
| `kg-thread-summaries` | Thread summaries | summary, subject, participants |
| `kg-attachment-summaries` | Attachment summaries | summary, filename |

### 3. Deploy the Web App

#### Build and Push Docker Image

```bash
az acr login --name <YOUR_ACR_NAME>

docker build -t <YOUR_ACR_NAME>.azurecr.io/tacitgraph:latest .
docker push <YOUR_ACR_NAME>.azurecr.io/tacitgraph:latest
```

#### Configure App Service

```bash
az webapp config container set \
  --name <YOUR_APP_SERVICE> \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --container-image-name <YOUR_ACR_NAME>.azurecr.io/tacitgraph:latest \
  --container-registry-url https://<YOUR_ACR_NAME>.azurecr.io
```

#### Set Environment Variables

```bash
az webapp config appsettings set \
  --name <YOUR_APP_SERVICE> \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --settings \
    AZURE_OPENAI_ENDPOINT="https://<YOUR_OPENAI_RESOURCE>.services.ai.azure.com/" \
    AZURE_OPENAI_API_KEY="<YOUR_OPENAI_KEY>" \
    AZURE_OPENAI_DEPLOYMENT="<YOUR_GPT4O_DEPLOYMENT>" \
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT="<YOUR_EMBEDDING_DEPLOYMENT>" \
    AZURE_OPENAI_API_VERSION="2025-01-01-preview" \
    AZURE_SEARCH_ENDPOINT="https://<YOUR_SEARCH_SERVICE>.search.windows.net" \
    AZURE_SEARCH_API_KEY="<YOUR_SEARCH_KEY>" \
    AZURE_SEARCH_INDEX_NAME="kg-chunks" \
    AZURE_SEARCH_ENTITY_INDEX_NAME="kg-entities" \
    AZURE_SEARCH_COMMUNITY_INDEX_NAME="kg-communities" \
    COSMOS_GREMLIN_ENDPOINT="wss://<YOUR_COSMOS_ACCOUNT>.gremlin.cosmos.azure.com:443/" \
    COSMOS_GREMLIN_KEY="<YOUR_COSMOS_KEY>" \
    COSMOS_DATABASE="<YOUR_DATABASE>" \
    COSMOS_GRAPH="<YOUR_GRAPH>" \
    ADLS_STORAGE_ACCOUNT="<YOUR_ADLS_ACCOUNT>" \
    ADLS_CONTAINER="<YOUR_CONTAINER>" \
    ADLS_STORAGE_KEY="<YOUR_ADLS_KEY>" \
    USE_ADLS_GRAPH="true" \
    PIPELINE_MODE="llm" \
    WEBSITES_PORT="8000" \
    WEBSITES_CONTAINER_START_TIME_LIMIT="600"
```

The thread- and attachment-summary indexes use the fixed names `kg-thread-summaries` and `kg-attachment-summaries`. The container start limit is raised because the app loads the Gold graph into memory at startup.

#### Restart and Verify

```bash
az webapp restart --name <YOUR_APP_SERVICE> --resource-group <YOUR_RESOURCE_GROUP>

# Check status
az webapp show \
  --name <YOUR_APP_SERVICE> \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --query "{state:state, defaultHostName:defaultHostName}" -o table

# Enable and tail logs
az webapp log config \
  --name <YOUR_APP_SERVICE> \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --docker-container-logging filesystem

az webapp log tail --name <YOUR_APP_SERVICE> --resource-group <YOUR_RESOURCE_GROUP>
```

The app will be available at `https://<YOUR_APP_SERVICE>.azurewebsites.net`

#### Redeployment

```bash
# Build and push new image
az acr build --registry <YOUR_ACR_NAME> --image tacitgraph:latest .

# Restart to pick up new image
az webapp restart --name <YOUR_APP_SERVICE> --resource-group <YOUR_RESOURCE_GROUP>

# Or use version tags to guarantee fresh pull:
az acr build --registry <YOUR_ACR_NAME> --image tacitgraph:v2 .
az webapp config container set \
  --name <YOUR_APP_SERVICE> \
  --resource-group <YOUR_RESOURCE_GROUP> \
  --container-image-name <YOUR_ACR_NAME>.azurecr.io/tacitgraph:v2
az webapp restart --name <YOUR_APP_SERVICE> --resource-group <YOUR_RESOURCE_GROUP>
```

### Run the App Locally Against Azure

```bash
uv sync --extra azure
uv run tacitgraph-app --mode llm      # uses the Azure endpoints in .env
```

### Development

```bash
uv sync --all-extras
uv run pre-commit install
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

CI runs linting, type checks, the test suite on Python 3.11 and 3.12, and a Docker build for every push and pull request.

## Contribute

Issues and pull requests are welcome. To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes (run `uv run pre-commit run --all-files` and `uv run pytest` first)
4. Push to the branch and open a Pull Request

For a laptop or single-server setup with local models, see **[tacitgraph](https://github.com/MRafiqAsim/tacitgraph)**.

## Privacy and Security

Mailbox archives contain personal data. The pipeline classifies and skips personal email, keeps all data inside your own Azure subscription, and never commits data or secrets (`data/` and `.env` are git-ignored). Prefer managed identities over account keys where your services support them, and make sure you are authorised to process the archives you load.

## Support

Did TacitGraph surface a piece of knowledge your inbox was hiding? Help fuel the next release with a [coffee (€5)](https://paypal.me/mrafiq89/5EUR) ☕ — or leave a ⭐ so the next team buried in PST files can find it too.

Want it tuned to your own Azure estate? [Fork it](https://github.com/MRafiqAsim/tacitgraph-azure/fork) and make it yours — that's what it's built for.

## License

[Apache License 2.0](LICENSE). The `src/tacitgraph/pathrag/` directory contains code adapted from [PathRAG](https://github.com/BUPT-GAMMA/PathRAG) and [LightRAG](https://github.com/HKUDS/LightRAG) under the MIT License; see [`NOTICE`](NOTICE).
