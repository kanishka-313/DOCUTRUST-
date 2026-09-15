# DocuTrust

**Enterprise advanced RAG platform with automated self-correction.**

Upload PDFs, ask a question. A retrieve → grade → decide → (rewrite + web fallback) → generate pipeline produces a cited answer. When the local corpus doesn't have what's needed, DocuTrust automatically falls back to the web — and tells you so.

---

## The Corrective RAG (CRAG) graph

```
                ┌──────────────┐
   Question ──▶ │  Retriever   │   pgvector cosine search, top-K chunks
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │   Grader     │   LLM scores each chunk for relevance
                └──────┬───────┘
                       ▼
                ┌──────────────┐
                │   Decision   │   ratio-based strategy selection
                └──────┬───────┘
            ┌──────────┼──────────┐
            ▼          ▼          ▼
        use_local   partial    web_fallback
            │          │          │
            │          ▼          ▼
            │     ┌──────────┐ ┌──────────┐
            │     │ Rewriter │ │ Rewriter │   reformulate for web search
            │     └────┬─────┘ └────┬─────┘
            │          ▼            ▼
            │     ┌──────────────────────┐
            │     │  Web Fallback (DDG)  │   DuckDuckGo, no API key
            │     └──────────┬───────────┘
            ▼                ▼
        ┌───────────────────────────────┐
        │  Generator (LLM + citations)  │   strict grounding rules
        └───────────────────────────────┘
                       │
                       ▼
              Answer + [S1][S2]…
```

Every stage emits live events via Server-Sent Events. The UI shows the pipeline running in real time.

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Angular 18 (standalone components, signals) |
| Backend | FastAPI, SQLAlchemy 2, async/await |
| Database | PostgreSQL 16 + **pgvector** |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (384-dim, runs on CPU) |
| LLM | OpenAI-compatible (Groq free tier recommended) |
| Web fallback | DuckDuckGo (no API key) |
| PDF parsing | pypdf |
| Real-time | Server-Sent Events |

**No model training.** Embeddings are pre-trained. The "intelligence" is in the graph orchestration, the grader prompt, and the strict generator prompt.

---

## Prerequisites

- Python 3.11+
- Node.js 20+ and npm
- Docker + Docker Compose
- Free Groq API key from https://console.groq.com (any OpenAI-compatible key works)

---

## Setup

### 1. Start pgvector-enabled Postgres

```bash
cd docutrust
docker compose up -d
```

Verify it's healthy:
```bash
docker ps    # should show docutrust-postgres
```

> ⚠️ **Important:** DocuTrust requires the `pgvector/pgvector:pg16` image, not the standard `postgres` image. The compose file uses the right one — don't substitute.

### 2. Backend

```bash
cd backend
python -m venv venv

# macOS / Linux
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env
```

Edit `backend/.env` and set `LLM_API_KEY=gsk_your_groq_key_here`.

Run the backend:
```bash
python main.py
```

**First start takes ~30 seconds** while sentence-transformers downloads the ~80MB embedding model (one-time, cached afterward). API at `http://localhost:8000`. Docs at `http://localhost:8000/docs`.

### 3. Frontend

```bash
cd frontend
npm install
npm start
```

Open `http://localhost:4200`.

---

## Usage

1. **Drop a PDF** (or several) onto the left pane's dropzone. The backend parses pages, chunks the text, embeds each chunk, and stores everything with the chunk vector in pgvector.
2. **Type a question** in the center panel and hit **Ask** (or ⌘/Ctrl + Enter).
3. **Watch the right pane**: stages light up in order — Retrieve → Grade → Decide → (maybe Rewrite + Web search) → Generate.
4. **Read the answer**, which is **grounded in cited sources** ([S1], [S2], …) listed below the body.

### Try this demo flow

- Upload any PDF you have — a textbook chapter, a research paper, an EULA.
- Ask something the document clearly answers → watch for the `use_local` strategy tag.
- Ask something **off-topic** for that document (e.g. "what's the current US treasury rate") → watch the pipeline detect insufficient local relevance, hit the rewriter, then DuckDuckGo, and produce a web-cited answer with a `web_fallback` tag.

That second demo is the moneymaker for your viva. It visibly proves the *corrective* in CRAG.

---

## Project structure

```
docutrust/
├── docker-compose.yml
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── .env.example
│   └── app/
│       ├── config.py
│       ├── database.py            # enables pgvector extension
│       ├── models.py              # Document, Chunk(Vector(384)), Query, TraceLog
│       ├── schemas.py
│       ├── api/routes.py          # REST + SSE
│       └── rag/
│           ├── embeddings.py      # sentence-transformers singleton
│           ├── ingest.py          # PDF → page-text → chunks
│           ├── retriever.py       # pgvector cosine search
│           ├── grader.py          # LLM-based per-chunk relevance grading
│           ├── rewriter.py        # query rewriter for web search
│           ├── web_fallback.py    # DuckDuckGo search
│           ├── generator.py       # grounded answer generation
│           ├── llm.py             # shared OpenAI-compatible client
│           └── orchestrator.py    # the CRAG graph + SSE broadcast
└── frontend/
    └── src/app/
        ├── app.component.{ts,html,scss}
        ├── services/api.service.ts
        └── components/
            ├── document-uploader/      # drag-and-drop PDFs
            ├── document-list/          # corpus inventory
            ├── query-panel/            # question input
            ├── agent-trace/            # live CRAG pipeline trace
            └── answer-view/            # answer + sources
```

---

## Database schema

Tables auto-create on first backend start. `pgvector` extension is enabled by `init_db()`.

**documents** — uploaded PDFs
| Column | Type |
|---|---|
| id | UUID PK |
| filename | VARCHAR(256) |
| pages | INT |
| chunk_count | INT |
| bytes | INT |
| uploaded_at | TIMESTAMP |

**chunks** — embedded text segments
| Column | Type |
|---|---|
| id | UUID PK |
| document_id | UUID FK → documents (CASCADE) |
| chunk_index | INT |
| page | INT |
| content | TEXT |
| embedding | **vector(384)** ← pgvector |

**queries** — user questions and final answers
| Column | Type |
|---|---|
| id | UUID PK |
| question | TEXT |
| answer | TEXT |
| status | VARCHAR — `pending` / `running` / `completed` / `failed` |
| decision | VARCHAR — `use_local` / `partial` / `web_fallback` |
| citations | JSONB |
| created_at, completed_at | TIMESTAMP |

**trace_logs** — per-stage event log (also the SSE source)
| Column | Type |
|---|---|
| id | SERIAL PK |
| query_id | UUID FK → queries (CASCADE) |
| agent | VARCHAR — `Retriever` / `Grader` / `Decision` / `Query Rewriter` / `Web Fallback` / `Generator` |
| status | VARCHAR — `started` / `completed` / `failed` |
| message | TEXT |
| payload | JSONB |
| created_at | TIMESTAMP |

---

## API endpoints

| Method | Path | Description |
|---|---|---|
| POST | `/api/documents` | Multipart PDF upload. Returns the indexed Document. |
| GET | `/api/documents` | List uploaded documents. |
| DELETE | `/api/documents/{id}` | Delete document and its chunks. |
| POST | `/api/queries` | Body `{"question": "..."}`. Starts CRAG pipeline as a background task. |
| GET | `/api/queries` | List recent queries. |
| GET | `/api/queries/{id}` | Full detail: answer, decision, citations, full trace log. |
| GET | `/api/queries/{id}/stream` | SSE — live trace events as the pipeline runs. |
| GET | `/health` | Health check. |

---

## How CRAG decides

Inside `orchestrator._decide()`:

```python
relevant_ratio = len(kept) / len(retrieved)
if relevant_ratio >= 0.5 and len(kept) >= 2:
    return "use_local"        # corpus is good enough, no web needed
if len(kept) >= 1:
    return "partial"          # something useful locally, augment with web
return "web_fallback"         # nothing usable locally, web only
```

You can tune the threshold via `RELEVANCE_THRESHOLD` in `.env`.

---

## Tuning

All knobs live in `backend/.env`:

```ini
CHUNK_SIZE=600              # chars per chunk
CHUNK_OVERLAP=80            # overlap between adjacent chunks
TOP_K=6                     # chunks retrieved per query
RELEVANCE_THRESHOLD=0.5     # fraction of chunks that must pass grader to skip web
EMBED_MODEL=sentence-transformers/all-MiniLM-L6-v2   # any HF sentence-transformer
```

For better quality (slower, larger model), try `BAAI/bge-base-en-v1.5` — but you'll need to **drop and recreate** the `chunks` table because the vector dimension changes from 384 to 768.

---

## Switching LLM providers

Same as MarketMind — any OpenAI-compatible endpoint:

```ini
# Groq (free, fast, recommended)
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile

# OpenAI
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini

# Local Ollama (set LLM_API_KEY=ollama)
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama3.1
```

---

## Troubleshooting

**`could not find function "vector"`** — your Postgres image isn't pgvector-enabled. Stop the container, run `docker compose down -v` (the `-v` drops the volume), and bring it up again with the right image.

**First backend start is slow / hangs** — it's downloading the embedding model. Wait ~30 seconds. Watch the terminal: it should print `Resolving config…` and similar.

**"No extractable text found"** — the PDF is a scanned image without OCR. DocuTrust doesn't OCR (out of scope). Run OCR through `ocrmypdf` first.

**Grader marks everything irrelevant** — the LLM is being too strict. Either lower `RELEVANCE_THRESHOLD`, or revise the grader prompt in `app/rag/grader.py` to require less evidence.

**DuckDuckGo returns nothing** — rate limit; wait a minute. For a more reliable demo, swap `duckduckgo-search` for SerpAPI or Tavily.

**CORS errors** — confirm `CORS_ORIGINS=http://localhost:4200` is in `backend/.env`.

---

## What to say in your viva

1. **Corrective RAG is a graph, not a chain** — the decision node routes between three strategies based on grader output. This is what separates CRAG from basic RAG.
2. **The grader is the safety mechanism** — without it, the system would happily generate answers from irrelevant chunks (the "hallucination via bad retrieval" failure mode).
3. **Cited grounding** — the generator prompt forbids using outside knowledge and forces inline `[S1]` markers. If sources are empty, the model is instructed to refuse. This is verifiable behavior, not vibes.
4. **Vector store is pgvector, not a separate service** — one less moving part, transactional with the rest of the data, queryable with regular SQL. Simpler to defend than "we use a vector DB."
5. **Pipeline is observable** — every stage writes a trace log with payload, both to the DB and the SSE stream. You can replay any past query and show the exact decision path.

---

## License

MIT. Educational/research use only — not legal or compliance advice.
