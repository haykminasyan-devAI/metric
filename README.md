# Armenian Voice AI Support Agent

A real-time voice AI customer support agent for Armenian banks, built with the open-source [LiveKit Agents](https://github.com/livekit/agents) framework. The agent understands and speaks Armenian and answers questions strictly about **credits, deposits, and branch locations** using a dense RAG pipeline with data scraped from official bank websites.

**Supported banks:** Ameriabank, Armeconombank (AEB), Amio Bank, Fast Bank



## Architecture & Decisions

### Why I chose Qwen as the default LLM

- I use `qwen/qwen3-next-80b-a3b-instruct` as the default model.
- During a previous Armenian RAG project (Armenian labor law), my instructor **Erik Arakelyan** advised me to test this model because it performs well in Armenian.
- I evaluated multiple model options, and in my tests Qwen gave the best overall quality for Armenian understanding and response relevance.
- I selected it from NVIDIA Build model catalog: [https://build.nvidia.com/models](https://build.nvidia.com/models).

### Retrieval architecture decision

- I initially implemented a hybrid retriever: **BM25 + dense embeddings (Metric) + neural re-ranker**.
- That setup increased response latency and became too slow for a voice assistant workflow.
- For faster and more stable real-time behavior, I switched the final default to **dense-only retrieval** with ChromaDB.
- Dense-only provided a better speed/quality trade-off for this submission.

---

## Architecture

```
User speaks Armenian
        |
        v
+-----------------------------------------------+
|           LIVEKIT (open-source)                |
|  Real-time audio transport over WebRTC         |
|  Manages connection, streaming, turn-taking    |
+---------------------+-------------------------+
                      | raw audio stream
                      v
+-----------------------------------------------+
|        VAD - Silero (local, offline)           |
|  Detects when the user stops speaking          |
+---------------------+-------------------------+
                      | audio segment
                      v
+-----------------------------------------------+
|      STT - OpenAI Whisper (whisper-1)          |
|  Transcribes Armenian speech to text           |
+---------------------+-------------------------+
                      | Armenian text query
                      v
+-----------------------------------------------+
|           DENSE RAG RETRIEVAL                  |
|                                                |
|  1. Dense search (ATE-1 embeddings)            |
|     via ChromaDB vector store                  |
|                                                |
|  Returns top-k relevant chunks with metadata   |
+---------------------+-------------------------+
                      | retrieved context
                      v
+-----------------------------------------------+
|    LLM (selectable - see Configuration)        |
|                                                |
|  Default: NVIDIA qwen3-next-80b-a3b-instruct  |
|  Alternative: OpenAI gpt-4o-mini               |
|                                                |
|  System prompt + retrieved context             |
|  -> generates grounded Armenian answer         |
+---------------------+-------------------------+
                      | Armenian text response
                      v
+-----------------------------------------------+
|         TTS - OpenAI TTS (tts-1)               |
|  Converts Armenian text to spoken audio        |
+---------------------+-------------------------+
                      | audio stream
                      v
              User hears the answer
```

---

## RAG Pipeline

Instead of injecting all bank data into the system prompt (which would exceed context limits for 4 banks), the agent uses a **Retrieval-Augmented Generation** pipeline:

### Embeddings
- **Default model:** `Metric-AI/armenian-text-embeddings-1` (ATE-1)
- **Vector store:** ChromaDB (local, persistent)

### Chunking Strategy
- **Product-aware:** Each loan or deposit product becomes its own chunk
- **Branch-aware:** Each bank branch (with address, hours, phone) is a separate chunk
- **Self-contained:** Every chunk is prefixed with `[Bank Name - Section]` for context
- **Size targets:** 600 chars average, 900 chars max, with line-boundary splitting

### Dense Retrieval
The system uses:

1. **Dense retrieval** - semantic similarity via Armenian embedding model + ChromaDB

This keeps retrieval simple and stable, with semantic matching as the default behavior.

### Special Retrieval Modes
- **Bank + section filtering:** Queries mentioning a specific bank and topic (e.g., "Fast Bank deposits") are filtered before retrieval
- **Strict field mode:** When users ask for specific fields (rate, amount, term), only exact matching lines are returned
- **Branch safety:** For branch queries, the system avoids false negatives by instructing the LLM to say "not found in data" instead of "does not exist"

---

## Configuration

### LLM Selection

The LLM is configurable via environment variables in `.env`:

| Variable | Values | Default |
|----------|--------|---------|
| `LLM_PROVIDER` | `nvidia`, `openai` | `nvidia` |
| `LLM_MODEL` | Any model name (leave empty for default) | Provider-specific |

**Provider defaults:**
- **nvidia:** `qwen/qwen3-next-80b-a3b-instruct` (recommended - strong Armenian performance)
- **openai:** `gpt-4o-mini` (faster, lower cost)

Example configurations:

```bash
# Use NVIDIA Qwen (default, best quality)
LLM_PROVIDER=nvidia
LLM_MODEL=

# Use OpenAI GPT-4o-mini
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini

# Use a specific OpenAI model
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o
```

### Embedding Model Selection

Set in `.env`:

```bash
# Default
EMBEDDING_MODEL=Metric-AI/armenian-text-embeddings-1
```

After changing embedding model, rebuild index:

```bash
python agent/build_index.py
```

### Retrieval Re-ranker Configuration

Re-ranker settings remain in `.env` for compatibility, but dense-only mode does not use them.

---

## Project Structure

```
armenian-voice-agent/
├── scraper/
│   ├── scrape_banks.py       # Scrapes credits, deposits, branches from bank websites
│   └── clean_data.py         # Removes noise, deduplicates, merges label-value pairs
├── agent/
│   ├── main.py               # LiveKit agent entrypoint (selectable LLM)
│   ├── prompts.py            # System prompt with guardrails (Armenian)
│   ├── rag.py                # Dense retriever (ChromaDB only)
│   └── build_index.py        # Builds ChromaDB index from bank_data_structured/
├── bank_data/                # Raw scraped text files (one per bank)
│   ├── ameriabank.txt
│   ├── aeb.txt
│   ├── amio.txt
│   └── fastbank.txt
├── bank_data_structured/     # Cleaned & structured data used for RAG indexing
│   ├── ameriabank.txt
│   ├── aeb.txt
│   ├── amio.txt
│   └── fastbank.txt
├── chroma_db/                # ChromaDB vector store (pre-built, included)
├── .env                      # Your API keys (never commit)
├── .env.example              # Template showing required keys
├── requirements.txt          # Python dependencies
└── README.md
```

---

## Setup Instructions

### Prerequisites

- Python 3.11 or higher
- Docker (for running LiveKit server locally)
- API keys: OpenAI (required for STT/TTS) + NVIDIA (required if using default LLM)

---

### Step 1 - Clone and install

```bash
git clone <your-repo-url>
cd armenian-voice-agent
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

---

### Step 2 - Configure environment variables

```bash
cp .env.example .env
```

Edit `.env` and set your API keys:

```bash
OPENAI_API_KEY=sk-your-openai-key
NVIDIA_API_KEY=nvapi-your-nvidia-key    # only if LLM_PROVIDER=nvidia
LLM_PROVIDER=nvidia                     # or "openai"
```

---

### Step 3 - Build the RAG index

```bash
python agent/build_index.py
```

This creates the ChromaDB vector index from the bank data already included in this repository.

---

### Step 4 - Run LiveKit server

```bash
docker run --rm \
  -p 7880:7880 \
  -p 7881:7881 \
  -p 7882:7882/udp \
  -e LIVEKIT_KEYS="devkey: secret" \
  livekit/livekit-server \
  --dev
```

Leave this terminal running.

---

### Step 5 - Run the agent

```bash
cd agent
python main.py dev
```

---

### Step 6 - Connect and test

Open the LiveKit Agents Playground:
[https://agents-playground.livekit.io](https://agents-playground.livekit.io)

Set server URL to `ws://localhost:7880`, API key `devkey`, secret `secret`. Start a session and speak in Armenian.

---

## Guardrails

The agent only answers questions about:
- **Credits and loans** (consumer, mortgage, auto, business, overdraft)
- **Deposits and savings** (term deposits, savings accounts)
- **Branch locations** (addresses, working hours, phone numbers)

Off-topic questions receive a polite refusal in Armenian. The agent does not give recommendations or compare banks.

---

## Adding a New Bank

1. Add a new entry to `BANK_CONFIGS` in `scraper/scrape_banks.py`:

```python
{
    "id": "new_bank",
    "name": "New Bank Name",
    "js_rendered": True,
    "follow_sublinks": True,
    "urls": {
        "credits":  ["https://newbank.am/hy/loans/..."],
        "deposits": ["https://newbank.am/hy/deposits/..."],
        "branches": ["https://newbank.am/hy/branches/..."],
    },
},
```

2. Re-run the pipeline:

```bash
python scraper/scrape_banks.py
python scraper/clean_data.py
python agent/build_index.py
```

3. Add bank name aliases to `_detect_bank()` in `agent/rag.py` for accurate bank detection from speech.

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Framework | LiveKit Agents (open-source) | Real-time voice pipeline |
| VAD | Silero | Voice activity detection (local) |
| STT | OpenAI Whisper | Armenian speech-to-text |
| LLM | NVIDIA Qwen / OpenAI GPT (selectable) | Armenian answer generation |
| TTS | OpenAI TTS (tts-1, alloy) | Text-to-speech |
| Embeddings | Metric-AI/armenian-text-embeddings-1 (default) | Armenian text embeddings |
| Vector DB | ChromaDB | Dense retrieval |
| Scraping | Playwright + BeautifulSoup | Bank website data extraction |
