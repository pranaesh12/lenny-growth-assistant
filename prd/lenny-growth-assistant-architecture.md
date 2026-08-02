# The Lenny Growth Assistant
## Software Architecture Document (SAD)

**Document status:** Pre-implementation architecture review
**Audience:** Senior software architects, staff engineers, AI platform engineers
**Author role:** Principal AI Software Architect / Lead Engineer

---

## Table of Contents

1. Project Analysis (Requirements, Risks, Assumptions)
2. System Architecture
3. Project Folder Structure
4. PostgreSQL Schema Design
5. REST API Design
6. AI Architecture (RAG Pipeline)
7. Agent Router Design
8. LLM Provider Abstraction
9. Implementation Milestones

---

# Step 1 — Project Analysis

Before designing anything, we need to pin down what "production-ready" actually obligates us to build, not just what the feature list implies. A conversational RAG app with essay generation and artifact rendering sounds like a weekend project until you interrogate the non-functional requirements — that's where most of the real engineering lives.

## 1.1 Functional Requirements (FR)

| ID | Requirement |
|----|-------------|
| FR-1 | Ingest Lenny's Podcast transcripts (bulk + incremental) from raw text/VTT/SRT/JSON sources |
| FR-2 | Chunk, embed, and index transcripts into a searchable vector knowledge base |
| FR-3 | Support multi-turn conversational Q&A grounded in transcript content (RAG) |
| FR-4 | Refuse to answer, or clearly flag, questions not groundable in the transcript corpus |
| FR-5 | Generate Ship30for30-style micro-essays from a topic or transcript excerpt |
| FR-6 | Generate artifacts in Markdown and HTML/CSS formats |
| FR-7 | Render generated artifacts inside the app (not just as raw text) |
| FR-8 | Support multiple, independent chat sessions per user |
| FR-9 | Persist all sessions, messages, and artifacts durably in PostgreSQL |
| FR-10 | Allow runtime switching of the LLM provider (Claude, OpenAI, Ollama) without code changes |
| FR-11 | Expose all functionality through a FastAPI backend with a documented REST contract |

## 1.2 Non-Functional Requirements (NFR)

| ID | Requirement | Why it matters |
|----|-------------|-----------------|
| NFR-1 | **Groundedness / low hallucination** | The entire value proposition is "answers strictly from transcripts." A single confidently-wrong answer breaks trust in the product. |
| NFR-2 | **Provider portability** | Model pricing, availability, and quality shift constantly. The app must survive a provider being swapped, deprecated, or rate-limited. |
| NFR-3 | **Latency** | RAG + generation adds real latency (retrieval + rerank + generation). Target first-token latency should be architected for, even if not optimized in v1. |
| NFR-4 | **Observability** | Every RAG failure mode (bad retrieval, bad chunking, prompt drift) is invisible without logging of retrieved chunks, prompts, and provider responses. |
| NFR-5 | **Data durability & migrations** | Conversations are a product asset. Schema must support Alembic-style migrations from day one. |
| NFR-6 | **Horizontal scalability** | FastAPI workers, vector store, and Postgres must scale independently. |
| NFR-7 | **Security** | API keys for Claude/OpenAI, session isolation between users, input sanitization for injected artifacts (HTML/CSS rendering is an XSS vector). |
| NFR-8 | **Testability** | Every module (ingestion, retrieval, router, provider adapter) must be unit-testable in isolation, which drives the interface-first design below. |
| NFR-9 | **Cost control** | Token usage (embeddings + generation) must be monitored and bounded; local Ollama must be a first-class fallback, not an afterthought. |
| NFR-10 | **Extensibility** | New "skills" (beyond Q&A, essay-writing, artifacts) should be addable without touching the router's core logic. |

## 1.3 Hidden Requirements

These are the requirements nobody states explicitly but that determine whether the system actually works in production:

1. **Transcript versioning.** Podcast transcripts get corrected/re-published. The ingestion pipeline needs idempotent re-ingestion (upsert by episode ID + content hash), not blind re-embedding.
2. **Citation/attribution.** "Answer strictly from transcript knowledge" implicitly requires the system to *show its work* — episode name, timestamp, guest — otherwise "strictly grounded" is an unverifiable claim.
3. **Artifact security sandboxing.** Rendering LLM-generated HTML/CSS in-app is a direct self-XSS vector. This must be sandboxed (iframe + CSP + sanitization), which is a hidden but critical requirement of FR-6/FR-7.
4. **Session-to-artifact linkage.** Artifacts are generated *inside* a chat session and must be retrievable later — this implies artifacts are a first-class DB entity, not a transient response field.
5. **Provider-specific tool/function-calling differences.** Claude, OpenAI, and Ollama each have different tool-calling and streaming semantics. The abstraction layer must normalize this or the "swap provider" requirement (FR-10) silently breaks.
6. **Context window budgeting.** Long conversations + large retrieved chunks can exceed context windows, especially for local Ollama models with smaller windows. Requires an explicit context-budget manager.
7. **Cold-start empty knowledge base.** Before ingestion runs, the app must degrade gracefully (say "no transcripts indexed yet") rather than hallucinate.
8. **Rate limiting / concurrency control** on both the LLM provider calls and the vector store, to avoid cascading failures under load.
9. **Configuration must be hot-swappable per session**, not just per deployment — a user should be able to pick "use Ollama for this chat" without restarting the server.

## 1.4 Risks

| Risk | Impact | Mitigation direction |
|------|--------|------------------------|
| Hallucinated answers presented as transcript-grounded | High (trust/credibility) | Strict RAG prompt contract + retrieval-confidence thresholding + "insufficient context" fallback |
| Vector store choice becomes a bottleneck at scale | Medium | Abstract vector store behind an interface (pgvector now, swappable to Qdrant/Pinecone later) |
| Provider abstraction leaks provider-specific behavior | High (breaks FR-10) | Strict adapter pattern + contract tests run against all three providers |
| XSS via rendered HTML/CSS artifacts | High (security) | Sandboxed iframe rendering, DOMPurify/HTML sanitization, strict CSP |
| Chunking strategy destroys semantic coherence of conversational transcripts | Medium (answer quality) | Speaker-aware, semantic/recursive chunking with overlap, not naive fixed-length splitting |
| Cost overrun from uncontrolled embedding/generation calls | Medium | Token/cost logging per request, caching of embeddings, dedup ingestion |
| Session state divergence between Postgres and in-memory agent state | Medium | Postgres as single source of truth; no server-side session memory beyond a cache |

## 1.5 Assumptions

- Transcripts are supplied as text (plain text, JSON, or subtitle formats) rather than requiring audio transcription (Whisper) in v1; this can be added as an ingestion source later without changing downstream architecture.
- Single-tenant or lightly multi-tenant deployment initially (auth can be simple in v1: API key or basic session cookie), with the schema designed to support full multi-tenancy later.
- PostgreSQL is available with the `pgvector` extension installable — used as *both* the relational store and vector store initially, to reduce operational surface area, with a documented path to a dedicated vector DB.
- Frontend is a modern SPA (React) consuming the FastAPI REST contract; SSR is out of scope for v1.
- "Claude/OpenAI" in the requirement means both are supported as hosted providers, in addition to local Ollama — three concrete adapters, not an open-ended plugin marketplace, for v1.

## 1.6 Technical Challenges

1. Designing a **provider-agnostic LLM interface** that still allows using each provider's native strengths (e.g., Claude's long context, OpenAI's function calling, Ollama's local/offline mode) without leaking provider-specific request/response shapes into business logic.
2. Building an **Agent Router** that reliably classifies intent (Q&A vs. essay vs. artifact) with low latency and without requiring a full extra LLM round-trip for every message where avoidable.
3. Making **RAG groundedness enforceable**, not just prompted — this requires retrieval-confidence scoring and a defined fallback behavior, not just "please only answer from context" in the system prompt.
4. **Safe rendering of LLM-generated HTML/CSS** artifacts in-browser without introducing XSS.
5. Keeping the **conversation + artifact data model** flexible enough for "future extensibility" (per the schema requirement) without over-engineering v1.

---

# Step 2 — System Architecture

## 2.1 High-Level Component Diagram (described)

```
┌──────────────────────────────────────────────────────────────────────┐
│                              CLIENT (SPA)                            │
│   Chat UI · Session List · Artifact Viewer (sandboxed iframe) ·      │
│   Provider/Model Switcher · Settings Panel                           │
└───────────────────────────────┬────────────────────────────────────--┘
                                 │ REST (JSON) / SSE for streaming
┌────────────────────────────────▼──────────────────────────────────────┐
│                         FASTAPI APPLICATION LAYER                     │
│  ┌───────────────┐ ┌───────────────┐ ┌───────────────┐ ┌────────────┐ │
│  │  Session API  │ │   Chat API    │ │ Artifact API  │ │ Config API │ │
│  └───────┬───────┘ └───────┬───────┘ └───────┬───────┘ └──────┬─────┘ │
│          │                 │                 │                │      │
│          └─────────────────┴──────┬──────────┴────────────────┘      │
│                                    ▼                                  │
│                         SERVICE / ORCHESTRATION LAYER                 │
│         ┌─────────────────────────────────────────────────┐          │
│         │                 AGENT ROUTER                    │          │
│         │  intent classification → skill dispatch          │          │
│         └───────┬───────────────┬───────────────┬──────────┘          │
│                 ▼               ▼               ▼                    │
│         ┌────────────┐  ┌──────────────┐  ┌────────────────┐         │
│         │ Transcript │  │ Ship30for30  │  │   Artifact      │         │
│         │  Q&A Skill │  │ Essay Skill  │  │ Generation Skill│         │
│         └─────┬──────┘  └──────┬───────┘  └────────┬────────┘         │
│               │                │                    │                 │
│               ▼                ▼                    ▼                 │
│         ┌─────────────────────────────────────────────────┐          │
│         │               PROMPT LAYER                       │          │
│         │  templated, versioned prompts + context builder  │          │
│         └───────────────────────┬─────────────────────────┘          │
│                                 ▼                                     │
│         ┌─────────────────────────────────────────────────┐          │
│         │            LLM ABSTRACTION LAYER                  │          │
│         │   ClaudeAdapter │ OpenAIAdapter │ OllamaAdapter    │          │
│         └───────────────────────┬─────────────────────────┘          │
└────────────────────────────────┬┴─────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼───────────────────────────┐
        ▼                         ▼                           ▼
┌───────────────┐        ┌────────────────┐         ┌────────────────────┐
│  PostgreSQL    │        │  Vector Store   │         │  External LLM APIs │
│  (sessions,    │        │  (pgvector /    │         │  Claude / OpenAI /  │
│  messages,     │        │  transcript     │         │  Ollama (local)     │
│  artifacts)    │        │  embeddings)    │         │                     │
└───────────────┘        └────────────────┘         └────────────────────┘
```

## 2.2 Component Rationale

**Frontend (SPA).** A separate frontend decouples release cycles from the backend and lets the artifact viewer be sandboxed independently (critical for the HTML/CSS XSS risk identified above). Chat UI uses SSE/streaming to keep perceived latency low despite RAG overhead.

**Backend (FastAPI).** FastAPI gives us async I/O (needed because we're fanning out to vector store + LLM provider, both I/O-bound), native Pydantic validation (data contracts for chat/artifact payloads matter a lot here), and automatic OpenAPI docs (useful given the API-heavy requirement set).

**Agent Router.** This is the architectural crux of the whole system. Without it, "Q&A vs essay vs artifact" becomes tangled if/else logic buried in a single endpoint. As its own component, it can be tested, tuned, and extended independently of the skills it dispatches to. Detailed design in Step 7.

**Prompt Layer.** Prompts are versioned, templated artifacts — not inline strings — because prompt regressions are a real production risk (a prompt tweak for the essay skill should never accidentally affect the Q&A skill's groundedness contract). This layer also owns **context budgeting** (fitting retrieved chunks + history into the active model's context window).

**LLM Abstraction Layer.** Exists solely to satisfy FR-10 and NFR-2. Every skill calls a single `LLMProvider` interface; provider selection is resolved once, at the edge, based on session/user config — never inside business logic.

**Database (PostgreSQL).** Single relational source of truth for sessions, messages, and artifacts. Chosen because conversational data is inherently relational (sessions → messages → artifacts) and because we need transactional guarantees when persisting a message + its artifact together.

**Vector Database.** Initially `pgvector` inside the same PostgreSQL instance — this reduces operational complexity (one database to run, back up, and migrate) while the retrieval interface is abstracted so we can swap to Qdrant/Weaviate/Pinecone later purely by implementing a new adapter, with zero change to the Q&A skill.

**Session Management.** Sessions are server-authoritative (stored in Postgres), not client-side state. The client only ever holds a `session_id`; all conversation state is rehydrated from the DB. This avoids the "session state divergence" risk from Step 1.

**Configuration Layer.** A single place (env vars + per-session override table) that governs which provider/model is active, chunking parameters, retrieval top-k, and feature flags. This is what makes "switching between Claude/OpenAI/Ollama" a config change, not a code change.

---

# Step 3 — Project Folder Structure

```
lenny-growth-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py                       # FastAPI app factory, middleware, router mounting
│   │   ├── config.py                     # Settings (Pydantic BaseSettings), env loading
│   │   │
│   │   ├── api/                          # Thin HTTP layer — no business logic
│   │   │   ├── deps.py                   # Shared FastAPI dependencies (db session, current config)
│   │   │   ├── v1/
│   │   │   │   ├── sessions.py           # Session endpoints
│   │   │   │   ├── chat.py               # Chat/message endpoints (incl. streaming)
│   │   │   │   ├── artifacts.py          # Artifact CRUD + render endpoints
│   │   │   │   ├── config.py             # Provider/model switch endpoints
│   │   │   │   └── health.py             # Liveness/readiness
│   │   │
│   │   ├── core/
│   │   │   ├── security.py               # API key handling, input sanitization helpers
│   │   │   ├── logging.py                # Structured logging setup
│   │   │   └── exceptions.py             # Domain exception types + handlers
│   │   │
│   │   ├── db/
│   │   │   ├── base.py                   # SQLAlchemy declarative base
│   │   │   ├── session.py                # Engine/session factory (async)
│   │   │   ├── models/
│   │   │   │   ├── session.py            # Session ORM model
│   │   │   │   ├── message.py            # Message ORM model
│   │   │   │   ├── artifact.py           # Artifact ORM model
│   │   │   │   ├── transcript.py         # Transcript + chunk ORM models
│   │   │   │   └── config.py             # SessionConfig / provider settings model
│   │   │   └── migrations/               # Alembic
│   │   │       ├── env.py
│   │   │       └── versions/
│   │   │
│   │   ├── schemas/                      # Pydantic request/response DTOs (mirrors models/)
│   │   │   ├── session.py
│   │   │   ├── message.py
│   │   │   ├── artifact.py
│   │   │   └── config.py
│   │   │
│   │   ├── repositories/                 # DB access layer (no business logic, just queries)
│   │   │   ├── session_repo.py
│   │   │   ├── message_repo.py
│   │   │   ├── artifact_repo.py
│   │   │   └── transcript_repo.py
│   │   │
│   │   ├── services/                     # Business logic / orchestration
│   │   │   ├── session_service.py
│   │   │   ├── chat_service.py           # Orchestrates router → skill → persistence
│   │   │   ├── artifact_service.py       # Artifact generation + sanitization
│   │   │   └── config_service.py
│   │   │
│   │   ├── agent/
│   │   │   ├── router.py                 # Agent Router — intent classification + dispatch
│   │   │   ├── intents.py                # Intent enum + classification schemas
│   │   │   └── skills/
│   │   │       ├── base_skill.py         # Abstract Skill interface
│   │   │       ├── transcript_qa_skill.py
│   │   │       ├── essay_skill.py        # Ship30for30-style essay generation
│   │   │       └── artifact_skill.py     # Markdown/HTML artifact generation
│   │   │
│   │   ├── rag/
│   │   │   ├── ingestion/
│   │   │   │   ├── loaders.py            # Transcript file loaders (txt/vtt/srt/json)
│   │   │   │   ├── chunker.py            # Speaker-aware semantic chunking
│   │   │   │   └── pipeline.py           # End-to-end ingest orchestration
│   │   │   ├── embeddings/
│   │   │   │   ├── base_embedder.py      # Abstract embedding interface
│   │   │   │   ├── openai_embedder.py
│   │   │   │   └── local_embedder.py     # e.g. sentence-transformers via Ollama/local
│   │   │   ├── vectorstore/
│   │   │   │   ├── base_vectorstore.py   # Abstract retrieval interface
│   │   │   │   └── pgvector_store.py
│   │   │   └── retriever.py              # Query embedding → search → rerank → context assembly
│   │   │
│   │   ├── prompts/
│   │   │   ├── prompt_builder.py         # Context budgeting + template rendering
│   │   │   ├── templates/
│   │   │   │   ├── qa_system.jinja
│   │   │   │   ├── essay_system.jinja
│   │   │   │   └── artifact_system.jinja
│   │   │   └── registry.py               # Versioned prompt registry
│   │   │
│   │   ├── llm/
│   │   │   ├── base_provider.py          # Abstract LLMProvider interface
│   │   │   ├── claude_provider.py
│   │   │   ├── openai_provider.py
│   │   │   ├── ollama_provider.py
│   │   │   ├── factory.py                # Resolves provider from config
│   │   │   └── types.py                  # Normalized request/response/streaming types
│   │   │
│   │   └── utils/
│   │       ├── html_sanitizer.py         # Artifact HTML/CSS sanitization
│   │       └── tokens.py                 # Token counting utilities per provider
│   │
│   ├── scripts/
│   │   ├── ingest_transcripts.py         # CLI entrypoint for bulk ingestion
│   │   └── seed_db.py
│   │
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_chunker.py
│   │   │   ├── test_agent_router.py
│   │   │   ├── test_llm_providers.py     # Contract tests run against all 3 adapters
│   │   │   └── test_html_sanitizer.py
│   │   ├── integration/
│   │   │   ├── test_chat_flow.py
│   │   │   └── test_ingestion_pipeline.py
│   │   └── conftest.py
│   │
│   ├── alembic.ini
│   ├── pyproject.toml
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/                     # ChatWindow, MessageBubble, StreamingIndicator
│   │   │   ├── sessions/                 # SessionSidebar, SessionListItem
│   │   │   ├── artifacts/                # ArtifactViewer (sandboxed iframe), MarkdownRenderer
│   │   │   └── settings/                 # ProviderSwitcher, ModelSelector
│   │   ├── hooks/
│   │   │   ├── useChatStream.ts
│   │   │   └── useSessions.ts
│   │   ├── api/
│   │   │   └── client.ts                 # Typed REST client (matches OpenAPI schema)
│   │   ├── pages/
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── infra/
│   ├── docker-compose.yml                # postgres+pgvector, backend, frontend, (ollama optional)
│   ├── nginx/
│   └── k8s/                              # future extensibility, not v1-blocking
│
├── data/
│   └── transcripts/                      # raw source transcripts (git-ignored / mounted volume)
│
├── .env.example
└── README.md
```

**Design intent:** the `repositories/` vs `services/` vs `api/` split enforces a strict layering discipline — HTTP concerns never touch the DB directly, and business logic never touches raw SQL. The `agent/`, `rag/`, `prompts/`, and `llm/` top-level packages mirror Steps 6–8 exactly, so the architecture document and the codebase stay in lockstep as the system grows.

---

# Step 4 — PostgreSQL Schema Design

## 4.1 Entity-Relationship Overview

```
sessions ──1:N── messages ──1:1(optional)── artifacts
   │
   └─1:1── session_configs

transcripts ──1:N── transcript_chunks (embedding column via pgvector)

messages ──N:1── transcript_chunks   (via message_citations, many-to-many)
```

## 4.2 Tables

### `sessions`
```sql
CREATE TABLE sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NULL,                 -- nullable in v1 (single/light-tenant), FK-ready for auth later
    title           TEXT NOT NULL DEFAULT 'New chat',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    archived_at     TIMESTAMPTZ NULL,
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb   -- future extensibility: tags, pinned, etc.
);
```

### `session_configs`
Kept separate from `sessions` so per-session provider/model overrides don't bloat the hot session-read path, and so config changes have their own audit trail.
```sql
CREATE TABLE session_configs (
    session_id      UUID PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    provider        TEXT NOT NULL DEFAULT 'claude',   -- 'claude' | 'openai' | 'ollama'
    model           TEXT NOT NULL DEFAULT 'claude-sonnet-4-6',
    temperature     NUMERIC(3,2) NOT NULL DEFAULT 0.4,
    retrieval_top_k SMALLINT NOT NULL DEFAULT 6,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### `messages`
```sql
CREATE TABLE messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content         TEXT NOT NULL,
    intent          TEXT NULL,               -- 'qa' | 'essay' | 'artifact' | NULL (set by Agent Router)
    provider_used   TEXT NULL,
    model_used      TEXT NULL,
    token_usage     JSONB NULL,              -- {"prompt": N, "completion": N}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_messages_session_id ON messages(session_id, created_at);
```

### `artifacts`
```sql
CREATE TABLE artifacts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    message_id      UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    type            TEXT NOT NULL CHECK (type IN ('markdown','html')),
    title           TEXT NOT NULL,
    content         TEXT NOT NULL,           -- raw markdown or sanitized HTML/CSS
    is_sanitized    BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX idx_artifacts_session_id ON artifacts(session_id);
```

### `transcripts`
```sql
CREATE TABLE transcripts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    episode_title   TEXT NOT NULL,
    episode_number  INTEGER NULL,
    guest_name      TEXT NULL,
    source_url      TEXT NULL,
    content_hash    TEXT NOT NULL UNIQUE,     -- enables idempotent re-ingestion
    published_at    DATE NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata        JSONB NOT NULL DEFAULT '{}'::jsonb
);
```

### `transcript_chunks`
```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE transcript_chunks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    transcript_id   UUID NOT NULL REFERENCES transcripts(id) ON DELETE CASCADE,
    chunk_index     INTEGER NOT NULL,
    speaker         TEXT NULL,
    start_time_sec  NUMERIC NULL,
    end_time_sec    NUMERIC NULL,
    content         TEXT NOT NULL,
    embedding       VECTOR(1536) NOT NULL,    -- dimension matches active embedding model
    embedding_model TEXT NOT NULL,            -- tracked so mixed-model corpora are detectable
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chunks_transcript_id ON transcript_chunks(transcript_id);
CREATE INDEX idx_chunks_embedding ON transcript_chunks
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
```

### `message_citations` (many-to-many: which chunks grounded which answer)
This table is what makes "answers strictly from transcript knowledge" *verifiable* rather than just prompted — every grounded answer has a durable, queryable link to its source chunks.
```sql
CREATE TABLE message_citations (
    message_id      UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    chunk_id        UUID NOT NULL REFERENCES transcript_chunks(id) ON DELETE CASCADE,
    similarity_score NUMERIC(5,4) NOT NULL,
    rank            SMALLINT NOT NULL,
    PRIMARY KEY (message_id, chunk_id)
);
```

## 4.3 Relationship Summary

- One **session** has many **messages** (1:N) and exactly one **session_config** (1:1).
- One **message** may produce zero or one **artifact** (1:0..1) — a normal Q&A message has none; an essay/artifact-skill message has one.
- One **message** cites zero or many **transcript_chunks** through `message_citations` (N:M), enabling full traceability of grounded answers.
- **transcripts** and **transcript_chunks** are independent of sessions entirely — the knowledge base is a shared, session-agnostic resource.
- `metadata JSONB` columns are deliberately present on every core entity — this is the "future extensibility" mechanism: new attributes (e.g., user feedback/thumbs-up, essay tone presets, artifact export formats) can be added without a migration, then promoted to real columns later if they need to be queried/indexed.

---

# Step 5 — REST API Design

Base path: `/api/v1`. All endpoints return JSON; chat responses support both a synchronous JSON mode and an SSE streaming mode (`Accept: text/event-stream`).

## 5.1 Session Endpoints

**`POST /sessions`** — create a new session
```json
// Request
{ "title": "Optional custom title" }

// Response 201
{
  "id": "9d3f...", "title": "New chat",
  "created_at": "2026-07-30T10:00:00Z",
  "config": { "provider": "claude", "model": "claude-sonnet-4-6" }
}
```

**`GET /sessions`** — list sessions (paginated)
```json
// Response 200
{
  "items": [
    { "id": "9d3f...", "title": "Ship30 essay on retention", "updated_at": "2026-07-30T10:04:00Z" }
  ],
  "next_cursor": null
}
```

**`GET /sessions/{session_id}`** — fetch a session with recent messages
**`PATCH /sessions/{session_id}`** — rename / archive a session
**`DELETE /sessions/{session_id}`** — hard delete (cascades to messages/artifacts)

## 5.2 Chat Endpoints

**`POST /sessions/{session_id}/messages`** — send a user message, get assistant reply
```json
// Request
{ "content": "What does Lenny's guests say about PMF signals?" }

// Response 200 (non-streaming)
{
  "message": {
    "id": "a1b2...",
    "role": "assistant",
    "content": "Several guests describe PMF as...",
    "intent": "qa",
    "provider_used": "claude",
    "citations": [
      { "episode_title": "Episode 142: ...", "start_time_sec": 812, "similarity_score": 0.83 }
    ]
  },
  "artifact": null
}
```

Streaming mode (`Accept: text/event-stream`) emits incremental `event: token` frames followed by a terminal `event: done` frame carrying the same structured payload as above, so the client always ends with a consistent final state regardless of transport.

**`GET /sessions/{session_id}/messages`** — full message history for a session (paginated)

## 5.3 Artifact Endpoints

**`GET /sessions/{session_id}/artifacts`** — list artifacts generated in a session
**`GET /artifacts/{artifact_id}`**
```json
// Response 200
{
  "id": "c4d5...", "type": "html",
  "title": "5 Lessons on Retention (Ship30 style)",
  "content": "<section>...</section>",
  "is_sanitized": true,
  "created_at": "2026-07-30T10:05:00Z"
}
```
**`GET /artifacts/{artifact_id}/render`** — returns the sandboxed, ready-to-embed HTML document (adds CSP meta tags, wraps in a minimal shell) for direct iframe `src`.
**`GET /artifacts/{artifact_id}/export?format=md|html`** — download as file.

## 5.4 Configuration Endpoints

**`GET /sessions/{session_id}/config`**
**`PATCH /sessions/{session_id}/config`**
```json
// Request
{ "provider": "ollama", "model": "llama3.1:70b" }

// Response 200
{ "provider": "ollama", "model": "llama3.1:70b", "temperature": 0.4, "retrieval_top_k": 6 }
```
**`GET /providers`** — lists available providers/models discovered from active config (e.g., which Ollama models are locally pulled).

## 5.5 Ingestion Endpoints (admin/back-office)

**`POST /transcripts/ingest`** — trigger ingestion of one or more transcript files (async job)
```json
// Request
{ "source_paths": ["data/transcripts/ep142.vtt"] }

// Response 202
{ "job_id": "job_88f1", "status": "queued" }
```
**`GET /transcripts/ingest/{job_id}`** — poll ingestion job status.

## 5.6 Health Endpoints

**`GET /health/live`** — process liveness (no dependencies checked)
**`GET /health/ready`** — checks DB connectivity, vector index availability, and configured LLM provider reachability
```json
{ "status": "ok", "checks": { "postgres": "ok", "vectorstore": "ok", "llm_provider": "ok" } }
```

---

# Step 6 — AI Architecture (RAG Pipeline)

## 6.1 Transcript Ingestion

1. **Loaders** normalize heterogeneous input formats (plain `.txt`, `.vtt`/`.srt` subtitle files, or structured JSON exports) into a single internal representation: an ordered list of `(speaker, start_time, end_time, text)` tuples per episode.
2. Each transcript is hashed (`content_hash`) so re-running ingestion on an unchanged file is a no-op — this satisfies the hidden requirement around transcript versioning/idempotency.
3. Metadata (episode title, guest, publish date) is extracted from filename conventions or an accompanying manifest file and stored on the `transcripts` row.

## 6.2 Chunking

Naive fixed-token chunking is explicitly rejected here because podcast transcripts are conversational — splitting mid-sentence or mid-thought severely degrades retrieval quality. Instead:

- **Speaker-turn-aware chunking**: chunk boundaries prefer speaker-turn boundaries first.
- **Semantic/recursive splitting** within long turns, targeting ~300–500 tokens per chunk with ~15% overlap, so a concept spanning a chunk boundary is still retrievable from either neighboring chunk.
- Each chunk retains `start_time_sec`/`end_time_sec` and `speaker`, which is what makes citation-by-timestamp (Step 4's hidden requirement) possible.

## 6.3 Embeddings

- Embedding generation goes through the same **provider abstraction philosophy** as generation: a `BaseEmbedder` interface with `OpenAIEmbedder` and a local embedder (via Ollama or `sentence-transformers`) as swappable implementations.
- `embedding_model` is stored per-chunk specifically so that if the embedding model is ever changed, the system can detect a **mixed-model corpus** and trigger re-embedding rather than silently mixing incompatible vector spaces (a real, easy-to-miss production bug).

## 6.4 Vector Store

- `pgvector` in v1, behind a `BaseVectorStore` interface (`upsert`, `search`, `delete_by_transcript`). This keeps the option open to move to a dedicated vector database later without touching the retriever or any skill code.
- An IVFFlat (or HNSW, depending on `pgvector` version) index on the embedding column keeps similarity search performant as the corpus grows.

## 6.5 Retrieval

The `retriever.py` module performs:
1. Embed the user's query (using the *same* embedding model as the corpus — enforced by checking `embedding_model` compatibility).
2. Vector similarity search, `top_k` from `session_configs.retrieval_top_k`.
3. **Confidence thresholding**: if the top result's similarity score falls below a configured floor, the retriever returns an explicit "insufficient context" signal rather than passing weak matches to the LLM — this is the concrete mechanism behind NFR-1 (groundedness), not just a prompt instruction.
4. Optional lightweight reranking (cross-encoder or an LLM-based rerank for small top_k) before context assembly.

## 6.6 Prompt Building

- The `PromptBuilder` assembles: system instructions (from the versioned template registry) + retrieved chunks (with citation markers) + conversation history, trimmed to fit the active model's context window (context budgeting, addressing the hidden requirement in 1.3.6).
- The **Q&A system prompt** explicitly instructs the model to answer only from the provided context and to say so plainly when the context is insufficient — reinforcing, not replacing, the retrieval-confidence gate in 6.5.

## 6.7 Skill Routing

Handled by the Agent Router (full design in Step 7) — determines which system prompt template and which downstream skill handles the request.

## 6.8 Response Generation

- The selected skill calls the `LLMProvider` interface (Step 8) with the assembled prompt.
- Response is post-processed: citations attached (from the chunks actually used), and — for artifact-producing skills — content is routed through the sanitizer before persistence.
- Everything (prompt, retrieved chunk IDs, provider, token usage, latency) is logged for observability (NFR-4).

---

# Step 7 — Agent Router Design

## 7.1 Purpose

The Agent Router is the single decision point that answers: *given this user message and session context, which skill should handle it?* Centralizing this avoids intent-detection logic leaking into every endpoint and skill.

## 7.2 Routing Algorithm

A **two-tier hybrid classifier** is used, prioritizing low latency and cost over always invoking a full LLM call:

**Tier 1 — Deterministic / rule-based fast path (no LLM call):**
- Explicit user commands or UI-driven intents short-circuit routing entirely. If the frontend sends an explicit `requested_skill` field (e.g., the user clicked "Generate Essay" or "Generate Artifact" button), the router trusts it directly — zero ambiguity, zero cost.
- Lightweight keyword/pattern heuristics catch high-confidence cases in free-text input (e.g., message matches `/write (an|a) essay/i`, `/ship\s?30/i` → essay intent; `/generate (a|an) (html|markdown|artifact|page)/i` → artifact intent). This is intentionally conservative — heuristics only fire on unambiguous patterns.

**Tier 2 — LLM-based intent classification (fallback):**
- If Tier 1 finds no confident match, the router issues a single, cheap, low-token classification call (small/fast model regardless of the session's chosen "chat" provider — this call always uses the fastest available model since it's a structured-output classification, not a creative task) with a strict JSON-schema output:
```json
{ "intent": "qa" | "essay" | "artifact", "confidence": 0.0-1.0 }
```
- If `confidence` is below a configured threshold, the router **defaults to `qa`** — the transcript Q&A skill is the safest fallback because it's the most conservative (bounded by retrieval, with an explicit "insufficient context" exit), whereas defaulting to essay/artifact generation on an ambiguous message risks generating unwanted content.

## 7.3 Dispatch

Once intent is resolved, the router instantiates the corresponding `Skill` (implementing a shared `BaseSkill.handle(session, message, config) -> SkillResult` interface) and delegates execution. Each skill independently:
- Selects its own prompt template (from the Prompt Layer).
- Decides whether it needs retrieval (Q&A always does; Essay may optionally pull supporting transcript context; Artifact generation typically consumes the *previous* assistant message rather than retrieving fresh).
- Returns a normalized `SkillResult` (`message_content`, `citations`, `artifact` (optional)) that the Chat Service persists uniformly regardless of which skill ran.

## 7.4 Why Not a Single Mega-Prompt?

A tempting alternative is one large system prompt asking the LLM to "decide and do everything in one call." This is rejected because: (a) it couples classification quality to generation quality — a model can classify well but write a mediocre essay, or vice versa, and a single call can't isolate which failed; (b) it prevents Tier-1 short-circuiting, so every message pays full generation latency/cost; (c) it makes the artifact-sanitization boundary fuzzy — we need to know structurally, before generation even starts, whether output will be HTML that requires sanitization.

## 7.5 Extensibility

Adding a new skill (e.g., "Competitive Analysis Skill") requires: (1) a new `BaseSkill` implementation, (2) a Tier-1 heuristic pattern and Tier-2 enum value, (3) a prompt template. The router's core loop never changes — this directly satisfies NFR-10.

---

# Step 8 — LLM Provider Abstraction

## 8.1 The Interface Contract

```
BaseLLMProvider (abstract)
 ├── generate(prompt: NormalizedPrompt, stream: bool) -> NormalizedResponse | AsyncIterator[Token]
 ├── embed(texts: list[str]) -> list[Vector]              # where the provider also serves embeddings
 ├── supports_streaming() -> bool
 ├── count_tokens(text: str) -> int
 └── health_check() -> bool
```

No skill, service, or route ever imports `anthropic`, `openai`, or an Ollama client directly — everything goes through `BaseLLMProvider`. This is what makes FR-10 real rather than aspirational: swapping providers is a config value change (`session_configs.provider`), resolved once by the `factory.py` at request time.

## 8.2 Normalization Responsibilities

Each concrete adapter (`ClaudeProvider`, `OpenAIProvider`, `OllamaProvider`) is responsible for absorbing provider-specific quirks so the rest of the system never sees them:

| Concern | How each adapter normalizes it |
|---|---|
| Message format | Converts internal `NormalizedPrompt` (system + turns) into each provider's native message schema |
| Streaming | Wraps SSE (OpenAI/Claude) or NDJSON (Ollama) into one common `AsyncIterator[Token]` shape |
| Token counting | Uses each provider's tokenizer (or a close approximation for Ollama-hosted models) but exposes a single `count_tokens` signature |
| Errors | Maps provider-specific exceptions (rate limits, context-length errors, auth errors) into a shared internal exception hierarchy (`ProviderRateLimitError`, `ProviderContextLengthError`, etc.) so callers handle failures uniformly |
| Function/tool calling | Only used internally for structured output (e.g., Tier-2 intent classification's JSON schema) — normalized via a shared `structured_output()` helper that adapts to each provider's native mechanism (tool-use for Claude, function-calling for OpenAI, JSON-mode/grammar constraints for Ollama) |

## 8.3 Provider Selection Flow

1. Request arrives with a `session_id`.
2. Chat Service loads `session_configs` for that session (`provider`, `model`, `temperature`).
3. `llm/factory.py` resolves the provider instance (`get_provider(name: str) -> BaseLLMProvider`), instantiated with the session's model and temperature.
4. That single provider instance flows through Prompt Layer → Skill → back to Chat Service — never re-resolved mid-request, guaranteeing consistency within a single turn.

## 8.4 Contract Testing

Because the abstraction is only trustworthy if all three adapters genuinely behave the same from the caller's perspective, `tests/unit/test_llm_providers.py` runs the **same test suite** parametrized across all three adapters (using recorded/mocked responses for CI, with an optional live-integration marker for manual runs against real APIs/local Ollama). This is what turns "provider portability" from a design intention into an enforced, regression-tested guarantee.

---

# Step 9 — Implementation Milestones

Each milestone below is scoped to be independently demoable and testable before moving to the next — deliberately sequenced so that later milestones never require rearchitecting earlier ones.

**M1 — Project scaffolding & health check**
FastAPI app factory, config layer, Docker Compose (Postgres+pgvector), `/health/live` and `/health/ready`. *Test:* `docker compose up` yields a green health check.

**M2 — Database schema & migrations**
All tables from Step 4 via Alembic; repositories layer with basic CRUD. *Test:* migration up/down round-trips cleanly; repository unit tests pass against a test DB.

**M3 — Session management API**
Full `sessions` CRUD endpoints (Step 5.1) wired to repositories/services. *Test:* create/list/get/patch/delete session via API integration tests.

**M4 — LLM abstraction layer (single provider first)**
`BaseLLMProvider` interface + `ClaudeProvider` implementation + factory. *Test:* a scripted "hello world" generate call, both streaming and non-streaming.

**M5 — LLM abstraction layer (remaining providers)**
Add `OpenAIProvider`, `OllamaProvider`; run the shared contract test suite across all three. *Test:* contract tests green for all adapters; config-driven provider switch verified end-to-end.

**M6 — Basic chat loop (no RAG yet)**
`POST /sessions/{id}/messages` persists user + assistant messages using the active provider directly (system prompt only, no retrieval). *Test:* multi-turn conversation persists correctly and reloads via `GET messages`.

**M7 — Transcript ingestion pipeline**
Loaders, speaker-aware chunker, embedding generation, `pgvector` storage; CLI script + async ingestion endpoint. *Test:* ingest a sample transcript, verify chunk count/embeddings/idempotent re-ingestion.

**M8 — Retrieval + grounded Q&A skill**
Retriever with confidence thresholding; Prompt Layer context assembly; Transcript Q&A Skill wired into the chat loop (router bypassed / hardcoded to `qa` for now). *Test:* ask a question with known transcript coverage → grounded answer with citations; ask an out-of-corpus question → explicit "insufficient context" response.

**M9 — Agent Router (Tier 1 + Tier 2)**
Full router with heuristic fast path and LLM-based fallback classification; QA skill now reached only via routing. *Test:* unit tests covering explicit-skill requests, heuristic matches, and ambiguous-message fallback-to-QA behavior.

**M10 — Ship30for30 essay skill**
Essay prompt template, optional supporting-context retrieval, skill implementation. *Test:* generate an essay from a topic prompt; verify router correctly routes essay-styled requests.

**M11 — Artifact generation skill + sanitization**
Markdown/HTML artifact generation, `html_sanitizer.py`, `artifacts` table persistence, export endpoints. *Test:* generate an HTML artifact containing a deliberately malicious payload in the prompt and verify it's neutralized before storage/render.

**M12 — Frontend: chat + sessions**
React SPA chat window, session sidebar, streaming message rendering. *Test:* manual E2E — create session, chat, switch sessions, history persists.

**M13 — Frontend: artifact viewer (sandboxed)**
Iframe-sandboxed artifact rendering with CSP, Markdown renderer for `.md` artifacts. *Test:* render an artifact with embedded `<script>` and confirm it does not execute.

**M14 — Configuration UI & provider switching end-to-end**
Settings panel wired to `/sessions/{id}/config`; live provider/model switch mid-session. *Test:* switch a live session from Claude → Ollama and confirm the next message uses the new provider without restarting anything.

**M15 — Observability & hardening**
Structured logging of prompts/retrievals/token usage, rate limiting on LLM calls, error-handling polish, cost/latency dashboards. *Test:* load test confirms graceful degradation (queued/backpressure) rather than cascading failure under concurrent load.

**M16 — Production readiness pass**
Security review (secrets handling, CSP audit, dependency scan), full Alembic migration dry-run against a prod-like dataset, deployment manifests (Docker/K8s), documentation pass. *Test:* fresh-environment deploy from scratch succeeds and passes `/health/ready`.

---

## Closing Notes for Reviewers

The architecture deliberately front-loads two things that are easy to under-invest in on a first pass: (1) a **provider abstraction with enforced contract tests**, because "swap the LLM" requirements silently rot without regression coverage across adapters; and (2) a **retrieval-confidence gate**, because "answer strictly from transcripts" is a trust claim, not a prompting style, and needs a concrete mechanism (not just instructions) to be defensible in production. Everything else in the design — the folder structure, the schema, the router — is built to keep those two guarantees intact as the system grows new skills and providers.
