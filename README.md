# AI Judge Backend

Complete FastAPI backend connecting the React frontend to your Python AI models.

---

## Architecture

```
React Frontend (Vite)
        │
        │  REST / JSON
        ▼
┌───────────────────────────────────────────────────────────┐
│                    FastAPI  (main.py)                      │
│                                                           │
│  POST /debate/{id}/message ──► Cleaner → LegalBERT → Advisor
│  GET  /debate/{id}/messages                               │
│  POST /judgment/{id}        ──► Queue trigger             │
│  GET  /judgment/{id}        ──► Poll result               │
│  POST /advisor/{id}/{side}  ──► Role-aware hint           │
└──────────────────┬────────────────────────────────────────┘
                   │ aio-pika (async)
                   ▼
        ┌──────────────────┐
        │    RabbitMQ      │
        │  arguments_queue │   ← one message per lawyer argument
        │  judgment_queue  │   ← fires once ≥10 args/side received
        └────────┬─────────┘
                 │
                 ▼
        ┌──────────────────┐
        │ JudgmentWorker   │   asyncio background task
        │  (buffers args)  │──► Mistral 7B (QLoRA) inference
        └──────────────────┘
                 │
                 ▼
        storage/judgments/{case_id}.json
```

---

## Quick Start

### 1. Prerequisites
- Python 3.11+
- Docker & Docker Compose (for RabbitMQ)
- NVIDIA GPU recommended (CPU fallback supported, but slow)

### 2. Clone & install
```bash
# Place your AI_Judge_Project/ folder alongside this backend/
# (it contains judge_model/ with the LoRA adapter)

cd ai_judge_backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure
```bash
cp .env.example .env
# Edit .env – set ADAPTER_PATH to point at your judge_model/ folder
```

### 4. Start RabbitMQ
```bash
docker-compose up rabbitmq -d
# Management UI: http://localhost:15672  (guest / guest)
```

### 5. Start the backend
```bash
uvicorn main:app --reload --port 8000
# Swagger UI: http://localhost:8000/docs
```

### 6. Connect the frontend
Replace `src/app/utils/api.js` with `frontend_api_updated.js` and add:
```
# .env (in your Vite project)
VITE_API_BASE_URL=http://localhost:8000
```

---

## Judgment Flow (step by step)

| Step | What happens |
|------|-------------|
| Lawyer types argument | `POST /debate/{id}/message` called |
| Argument cleaned | Regex + unicode normalisation (`argument_cleaner.py`) |
| NLP scored | LegalBERT cosine similarity → 0-100 score |
| Advisor hint generated | Role-specific Mistral Instruct hint returned to UI |
| Argument saved to JSON | `storage/debates/{case_id}.json` |
| Published to RabbitMQ | `arguments_queue` receives one message |
| Worker buffers | Counts A and B arguments in memory |
| Threshold reached (≥10/side) | `judgment_queue` receives trigger |
| Mistral 7B runs | Bulk processes all arguments → structured verdict |
| Result saved | `storage/judgments/{case_id}.json` |
| Frontend polls | `GET /judgment/{id}` → complete result shown |

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/debate/{case_id}/message` | Submit lawyer argument |
| `GET`  | `/debate/{case_id}/messages` | Get full debate history |
| `GET`  | `/debates` | List all debates |
| `POST` | `/judgment/{case_id}` | Trigger judgment |
| `GET`  | `/judgment/{case_id}` | Poll judgment result |
| `POST` | `/advisor/{case_id}/{side}` | Get advisor hint (A or B) |
| `GET`  | `/health` | Health check + queue status |

Interactive docs: **http://localhost:8000/docs**

---

## Folder Structure

```
ai_judge_backend/
├── main.py                    # FastAPI app + lifespan
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── frontend_api_updated.js    # Drop-in replacement for src/app/utils/api.js
│
├── config/
│   └── settings.py            # Pydantic settings (reads .env)
│
├── api/
│   └── routes/
│       ├── debate.py          # /debate/* routes
│       ├── judgment.py        # /judgment/* routes
│       └── advisor.py         # /advisor/* route
│
├── models/
│   ├── schemas.py             # Pydantic request/response models
│   └── database.py            # JSON file persistence layer
│
├── services/
│   ├── argument_cleaner.py    # Text preprocessing
│   ├── nlp_scorer.py          # LegalBERT accuracy scoring
│   ├── ai_advisor.py          # Role-aware AI advisor
│   ├── judge_model.py         # Mistral 7B + LoRA inference
│   └── message_queue.py       # RabbitMQ manager (aio-pika)
│
├── workers/
│   └── judgment_worker.py     # Background consumer + threshold logic
│
└── storage/
    ├── debates/               # {case_id}.json  – debate state
    └── judgments/             # {case_id}.json  – judgment results
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `RABBITMQ_URL` | `amqp://guest:guest@localhost:5672/` | RabbitMQ connection |
| `BASE_MODEL` | `mistralai/Mistral-7B-v0.1` | HuggingFace base model |
| `ADAPTER_PATH` | `AI_Judge_Project/judge_model` | Path to LoRA adapter |
| `LEGAL_BERT_MODEL` | `nlpaueb/legal-bert-base-uncased` | NLP scorer |
| `ADVISOR_MODEL` | `mistralai/Mistral-7B-Instruct-v0.2` | Advisor model |
| `MIN_ARGUMENTS_FOR_JUDGMENT` | `10` | Min args per side before verdict |
| `CORS_ORIGINS` | `["http://localhost:5173"]` | Allowed frontend origins |

---

## GPU Notes

- The backend auto-detects CUDA. Without a GPU it falls back to heuristic NLP scoring and a mock judgment.
- For Docker GPU support uncomment the `deploy.resources` block in `docker-compose.yml` and ensure `nvidia-container-toolkit` is installed.

