# Lenny Growth Assistant — Database Design

**Document:** `docs/database.md`
**Status:** Implementation-ready
**Audience:** Backend engineers, DBAs, infrastructure reviewers
**Related documents:** PRD, System Architecture

---

## 1. Database Overview

The Lenny Growth Assistant uses a **polyglot persistence** model: one system of record for structured, relational, transactional data (PostgreSQL) and one specialized system for high-dimensional vector search (ChromaDB). Each store is used only for what it is architecturally good at.

### 1.1 What lives in PostgreSQL

PostgreSQL is the **system of record** for all structured application state:

- Chat sessions and their metadata
- Full conversation history (every user/assistant message)
- Generated artifacts (HTML/Markdown) and their content
- Metadata describing ingested transcripts (source, size, status, chunk counts)
- Any relational, queryable, transactional data that needs ACID guarantees, foreign key integrity, joins, and precise filtering/sorting

PostgreSQL is authoritative — if PostgreSQL and ChromaDB ever disagree, PostgreSQL wins, and ChromaDB can be rebuilt from it.

### 1.2 What lives in ChromaDB

ChromaDB stores **only vector embeddings and the minimal metadata needed to filter/retrieve them**:

- Text chunk embeddings generated from ingested transcripts
- A copy of the chunk text (required by Chroma to return results), treated as a denormalized cache, not the source of truth
- Lightweight filterable metadata (`transcript_id`, `session_id`, `chunk_index`, etc.) that mirrors foreign keys in PostgreSQL

### 1.3 Why this split

| Concern | PostgreSQL | ChromaDB |
|---|---|---|
| ACID transactions | Yes | No |
| Relational integrity (FKs, joins) | Yes | No |
| Full-text/structured filtering | Yes (native) | Limited (metadata filters only) |
| Approximate nearest-neighbor vector search | No (not efficient at scale) | Yes (purpose-built, HNSW index) |
| Source of truth for business data | Yes | No |
| Rebuildable from another store | N/A | Yes, from PostgreSQL `transcript_metadata` + raw source |

**Rule of thumb enforced throughout this design:** embeddings and vector-index internals never enter PostgreSQL; conversation/session/artifact/business data never becomes the source of truth inside ChromaDB. ChromaDB is treated as a disposable, rebuildable index, not a database of record.

---

## 2. Entity Relationship Diagram

```
                              ┌────────────────────────┐
                              │        sessions         │
                              ├────────────────────────┤
                              │ PK id (UUID)             │
                              │    title                 │
                              │    llm_provider           │
                              │    llm_model               │
                              │    status                  │
                              │    created_at               │
                              │    updated_at                │
                              │    metadata (JSONB)            │
                              └───────────┬────────────────┘
                                          │ 1
                                          │
                                          │ N
                              ┌───────────▼────────────────┐
                              │         messages            │
                              ├─────────────────────────────┤
                              │ PK id (UUID)                  │
                              │ FK session_id ──────────────► sessions.id
                              │    role (user/assistant/system)│
                              │    content (TEXT)               │
                              │    llm_provider                  │
                              │    llm_model                      │
                              │    token_count                     │
                              │    created_at                       │
                              │    metadata (JSONB)                  │
                              └───────────┬───────────────────────┘
                                          │ 1
                                          │
                                          │ 0..N
                              ┌───────────▼──────────────────────┐
                              │            artifacts               │
                              ├────────────────────────────────────┤
                              │ PK id (UUID)                          │
                              │ FK message_id ───────────────────────► messages.id
                              │ FK session_id ───────────────────────► sessions.id
                              │    artifact_type (html/markdown)        │
                              │    title                                  │
                              │    content (TEXT)                          │
                              │    version                                  │
                              │    created_at                                │
                              │    metadata (JSONB)                           │
                              └────────────────────────────────────────────────┘

                              ┌──────────────────────────────┐
                              │      transcript_metadata        │
                              ├──────────────────────────────────┤
                              │ PK id (UUID)                        │
                              │ FK session_id ──────────────────────► sessions.id  (nullable)
                              │    source_filename                    │
                              │    source_type                          │
                              │    file_size_bytes                        │
                              │    chunk_count                              │
                              │    embedding_model                            │
                              │    chroma_collection_name                       │
                              │    ingestion_status                               │
                              │    created_at                                       │
                              │    updated_at                                         │
                              │    metadata (JSONB)                                     │
                              └───────────────────┬─────────────────────────────────────┘
                                                  │ references (logical, cross-store)
                                                  ▼
                              ┌──────────────────────────────────┐
                              │     ChromaDB Collection             │
                              │  (transcript_chunks / per-session)   │
                              ├──────────────────────────────────────┤
                              │  id = chunk_id (string)                 │
                              │  embedding = vector[float]                │
                              │  document = chunk text                      │
                              │  metadata = {transcript_id, session_id,       │
                              │              chunk_index, ...}                  │
                              └──────────────────────────────────────────────────┘
```

**Cardinalities**
- One `session` → many `messages` (1:N)
- One `message` → zero or more `artifacts` (1:N, optional)
- One `session` → many `artifacts` (1:N, denormalized FK for direct session-level artifact queries)
- One `session` → zero or more `transcript_metadata` rows (1:N, optional; a session may or may not have RAG sources attached)
- One `transcript_metadata` row → many ChromaDB chunk vectors (1:N, logical reference via `transcript_id` metadata field, not a DB-enforced FK)

---

## 3. Database Tables

### 3.1 `sessions`

**Purpose:** Represents a single chat/conversation session (a "thread" of interaction), including which LLM provider/model is active and session-level metadata.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, `DEFAULT gen_random_uuid()` |
| `title` | VARCHAR(255) | NOT NULL, `DEFAULT 'New Chat'` |
| `llm_provider` | VARCHAR(50) | NOT NULL — e.g. `openai`, `anthropic`, `google` |
| `llm_model` | VARCHAR(100) | NOT NULL — e.g. `claude-sonnet-5` |
| `status` | VARCHAR(20) | NOT NULL, `DEFAULT 'active'`, CHECK IN (`active`, `archived`, `deleted`) |
| `created_at` | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` |
| `updated_at` | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` |
| `metadata` | JSONB | NOT NULL, `DEFAULT '{}'` |

**Primary Key:** `id`
**Foreign Keys:** none (root entity)
**Indexes:**
- `idx_sessions_status` on `status`
- `idx_sessions_created_at` on `created_at DESC` (for recency sorting/pagination)
- GIN index on `metadata` for flexible metadata queries

**Relationships:** parent of `messages`, `artifacts`, `transcript_metadata`
**Constraints:** `status` CHECK constraint; `updated_at` maintained via trigger on row update

---

### 3.2 `messages`

**Purpose:** Stores every message exchanged within a session — user prompts, assistant responses, and optional system messages — forming the persistent conversation history.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, `DEFAULT gen_random_uuid()` |
| `session_id` | UUID | NOT NULL, FK → `sessions.id` |
| `role` | VARCHAR(20) | NOT NULL, CHECK IN (`user`, `assistant`, `system`) |
| `content` | TEXT | NOT NULL |
| `llm_provider` | VARCHAR(50) | NULL (set for `assistant` messages) |
| `llm_model` | VARCHAR(100) | NULL (set for `assistant` messages) |
| `token_count` | INTEGER | NULL, CHECK (`token_count >= 0`) |
| `created_at` | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` |
| `metadata` | JSONB | NOT NULL, `DEFAULT '{}'` |

**Primary Key:** `id`
**Foreign Keys:** `session_id` → `sessions.id` ON DELETE CASCADE
**Indexes:**
- `idx_messages_session_id` on `session_id`
- `idx_messages_session_created` composite on `(session_id, created_at)` — primary pagination path for loading a conversation in order
- `idx_messages_role` on `role` (optional, for analytics filters)

**Relationships:** child of `sessions`; parent of `artifacts` (0..N)
**Constraints:** `role` CHECK constraint; `content` NOT NULL (empty string allowed, NULL not allowed)

---

### 3.3 `artifacts`

**Purpose:** Stores generated artifacts (HTML or Markdown documents) produced by the assistant in response to a message — e.g., a generated report, code snippet, or formatted document.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, `DEFAULT gen_random_uuid()` |
| `message_id` | UUID | NOT NULL, FK → `messages.id` |
| `session_id` | UUID | NOT NULL, FK → `sessions.id` (denormalized for direct session queries) |
| `artifact_type` | VARCHAR(20) | NOT NULL, CHECK IN (`html`, `markdown`) |
| `title` | VARCHAR(255) | NOT NULL, `DEFAULT 'Untitled Artifact'` |
| `content` | TEXT | NOT NULL |
| `version` | INTEGER | NOT NULL, `DEFAULT 1`, CHECK (`version >= 1`) |
| `created_at` | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` |
| `metadata` | JSONB | NOT NULL, `DEFAULT '{}'` |

**Primary Key:** `id`
**Foreign Keys:**
- `message_id` → `messages.id` ON DELETE CASCADE
- `session_id` → `sessions.id` ON DELETE CASCADE

**Indexes:**
- `idx_artifacts_message_id` on `message_id`
- `idx_artifacts_session_id` on `session_id`
- `idx_artifacts_type` on `artifact_type`

**Relationships:** child of `messages` and (denormalized) child of `sessions`
**Constraints:** `artifact_type` CHECK constraint; `session_id` must equal the `session_id` of the parent message (enforced at application layer or via trigger — see §13)

---

### 3.4 `transcript_metadata`

**Purpose:** Stores metadata about a document/transcript ingested for Retrieval-Augmented Generation. **No embeddings or vectors are stored here** — this table only tracks what was ingested, how, and where its vectors live in ChromaDB.

| Column | Type | Constraints |
|---|---|---|
| `id` | UUID | PK, `DEFAULT gen_random_uuid()` |
| `session_id` | UUID | NULL, FK → `sessions.id` (nullable — a transcript can be global/shared, not tied to one session) |
| `source_filename` | VARCHAR(500) | NOT NULL |
| `source_type` | VARCHAR(50) | NOT NULL, CHECK IN (`pdf`, `txt`, `md`, `docx`, `url`, `other`) |
| `file_size_bytes` | BIGINT | NULL, CHECK (`file_size_bytes >= 0`) |
| `chunk_count` | INTEGER | NOT NULL, `DEFAULT 0`, CHECK (`chunk_count >= 0`) |
| `embedding_model` | VARCHAR(100) | NOT NULL — e.g. `text-embedding-3-large` |
| `chroma_collection_name` | VARCHAR(255) | NOT NULL |
| `ingestion_status` | VARCHAR(20) | NOT NULL, `DEFAULT 'pending'`, CHECK IN (`pending`, `processing`, `completed`, `failed`) |
| `created_at` | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` |
| `updated_at` | TIMESTAMPTZ | NOT NULL, `DEFAULT now()` |
| `metadata` | JSONB | NOT NULL, `DEFAULT '{}'` |

**Primary Key:** `id`
**Foreign Keys:** `session_id` → `sessions.id` ON DELETE SET NULL
**Indexes:**
- `idx_transcript_session_id` on `session_id`
- `idx_transcript_status` on `ingestion_status`
- `idx_transcript_collection` on `chroma_collection_name`

**Relationships:** optional child of `sessions`; logical (not FK-enforced) parent of chunk vectors in ChromaDB, referenced via `id` as `transcript_id` in Chroma metadata
**Constraints:** `source_type` and `ingestion_status` CHECK constraints; `chroma_collection_name` NOT NULL so every row is traceable to its vector store location

---

## 4. ChromaDB Collection Design

ChromaDB is not a relational store — its "schema" is a set of conventions this project enforces at the application layer.

### 4.1 Collection naming

- **One collection per logical corpus**, not per session, to keep Chroma's collection count manageable:
  - `transcript_chunks` — the default, shared collection for all ingested RAG source material.
- If per-session isolation is later required (e.g., private user documents), the convention is:
  `session_{session_id}_chunks` — created lazily, referenced by `transcript_metadata.chroma_collection_name`.
- The collection name actually used for a given transcript is always recorded in `transcript_metadata.chroma_collection_name` — never hardcoded or inferred at query time.

### 4.2 Document IDs and Chunk IDs

- **Chunk ID format:** `{transcript_id}_{chunk_index}` — e.g. `3f2a1c9e-...__0007`
  - `transcript_id` matches `transcript_metadata.id` (UUID) exactly, enabling a direct join back to PostgreSQL.
  - `chunk_index` is a zero-padded, zero-based sequential integer within the transcript, preserving original document order.
- Chunk IDs are deterministic and idempotent: re-ingesting the same transcript with the same chunking parameters regenerates the same IDs, so upserts overwrite rather than duplicate.

### 4.3 Metadata fields stored per vector

Each ChromaDB entry carries a minimal, filterable metadata payload:

| Field | Type | Purpose |
|---|---|---|
| `transcript_id` | string (UUID) | Join key back to `transcript_metadata.id` |
| `session_id` | string (UUID) or `null` | Enables session-scoped retrieval filters |
| `chunk_index` | int | Ordering / neighbor-chunk retrieval |
| `source_filename` | string | Human-readable provenance for citations |
| `created_at` | string (ISO 8601) | Freshness filtering |

The `document` field stores the raw chunk text (required by Chroma for retrieval); this is a **denormalized cache** of content whose canonical existence is the original source file, not a new source of truth.

### 4.4 Embedding model assumptions

- A single embedding model is used per collection at any given time (mixing embedding spaces in one collection produces meaningless similarity scores).
- The exact model name/version used to embed a transcript is recorded in `transcript_metadata.embedding_model`, so:
  - Retrieval code can validate the query embedding was produced by the same model before searching.
  - A model migration can be executed as a controlled backfill (re-embed, write to a new collection, cut over, then deprecate the old collection) without silently corrupting search quality.
- Default assumption for this project: OpenAI `text-embedding-3-large` (1536 or 3072 dims, configurable) or an equivalent provider-neutral embedding model; the schema does not hardcode a dimension, since Chroma manages that per collection.

---

## 5. Relationships

### 5.1 Session → Messages
A `session` owns an ordered sequence of `messages`. This is a strict 1:N relationship enforced by `messages.session_id` with `ON DELETE CASCADE` — deleting a session deletes its full conversation history. Ordering is by `created_at` (with `id` as a tiebreaker for same-timestamp inserts), not by a separate sequence column, since PostgreSQL timestamp precision (microseconds) is sufficient at this scale.

### 5.2 Message → Artifact
A `message` (always an `assistant` message in practice, enforced at application layer) may produce zero, one, or several `artifacts` — e.g., a single response could include both an HTML and a Markdown artifact, or multiple versions of one artifact type. This is 1:N with `ON DELETE CASCADE`: deleting a message deletes its artifacts. `artifacts.session_id` is denormalized from the parent message purely to avoid a join when listing "all artifacts in this session," a common UI operation.

### 5.3 Transcript → Chroma
A `transcript_metadata` row describes one ingested source document. Its chunks live in ChromaDB as separate vector entries, connected **logically, not via a database foreign key** (ChromaDB cannot enforce PostgreSQL FKs). The connection is maintained by convention:
- PostgreSQL is authoritative for "what was ingested, when, and its status."
- ChromaDB is authoritative for "the vectors and their nearest-neighbor structure."
- If a `transcript_metadata` row is deleted, the application layer is responsible for issuing a corresponding delete against Chroma (`where={"transcript_id": id}`) — see §7.5 for the enforced two-phase deletion strategy.

---

## 6. Indexing Strategy

### 6.1 Primary indexes
Every table's primary key (`id UUID`) is automatically backed by a unique B-tree index — the basis for all point lookups (`WHERE id = $1`).

### 6.2 Foreign key indexes
Every foreign key column is explicitly indexed (PostgreSQL does **not** auto-index FK columns):
- `messages.session_id`
- `artifacts.message_id`, `artifacts.session_id`
- `transcript_metadata.session_id`

This is critical — without these, cascading deletes and join queries (e.g., "load all messages for a session") degrade to sequential scans as tables grow.

### 6.3 Search optimization
- **Composite index** `(session_id, created_at)` on `messages` supports the single most frequent query in the system: "give me this session's messages in order," satisfied entirely by an index scan with no sort step.
- **GIN indexes on JSONB `metadata` columns** (`sessions`, `messages`, `artifacts`, `transcript_metadata`) support ad-hoc metadata filtering (e.g., `metadata @> '{"pinned": true}'`) without a full scan.
- ChromaDB's own HNSW index handles approximate nearest-neighbor search; PostgreSQL indexes never attempt to substitute for vector similarity search.

### 6.4 Sorting
- `sessions` sorted by `created_at DESC` or `updated_at DESC` for "recent chats" views — backed by `idx_sessions_created_at`.
- `messages` sorted by `created_at ASC` within a session — backed by the composite index above.

### 6.5 Pagination
- **Keyset (cursor) pagination** is the standard for `messages` and `sessions`, not `OFFSET/LIMIT`:
  ```sql
  SELECT * FROM messages
  WHERE session_id = $1 AND created_at > $2
  ORDER BY created_at ASC
  LIMIT 50;
  ```
  This avoids the performance cliff of `OFFSET` on large conversations and remains stable even if rows are inserted concurrently.

---

## 7. Data Lifecycle

### 7.1 Session creation
1. Application inserts a row into `sessions` with `llm_provider`/`llm_model` chosen by the user (or defaults) and `status = 'active'`.
2. `title` defaults to `'New Chat'` and is later updated (e.g., auto-generated from the first message) via an `UPDATE` that also bumps `updated_at`.

### 7.2 Message creation
1. On each turn, a `user` message row is inserted first (so it's durable even if the LLM call fails).
2. The assistant's response is inserted as a second row with `role = 'assistant'`, the `llm_provider`/`llm_model` actually used, and `token_count` from the provider's usage metadata.
3. `sessions.updated_at` is refreshed (trigger, see §9) so "recent sessions" ordering reflects real activity.

### 7.3 Artifact creation
1. When an assistant response contains a renderable HTML/Markdown block, the application inserts an `artifacts` row referencing the assistant `message_id` (and the denormalized `session_id`).
2. If the user asks for a revision of the same artifact, a **new row** is inserted with the same logical artifact identity tracked via `metadata->>'artifact_key'` and an incremented `version` — artifacts are append-only/versioned, never overwritten in place, to preserve history.

### 7.4 Transcript ingestion
1. A `transcript_metadata` row is inserted with `ingestion_status = 'pending'` as soon as a file is accepted (so the UI can show progress).
2. A background worker chunks the document, generates embeddings, and upserts vectors into the target ChromaDB collection.
3. On success: `ingestion_status = 'completed'`, `chunk_count` set to the actual number of chunks written.
4. On failure: `ingestion_status = 'failed'`, error detail recorded in `metadata->>'error'`; no partial/orphaned vectors are left in Chroma (the worker deletes any partially-written chunks for that `transcript_id` before marking failed).

### 7.5 Deletion strategy
- **Soft delete for sessions** (`status = 'deleted'`) is the default user-facing action — reversible, and keeps referential/audit history intact.
- **Hard delete** (actual `DELETE FROM sessions WHERE id = $1`) is a separate, privileged operation (e.g., a retention job or explicit "permanently delete" action) that relies on `ON DELETE CASCADE` to remove all `messages` and `artifacts` transactionally.
- **Two-phase deletion for transcripts**, since Chroma isn't transactional with Postgres:
  1. Delete the vectors from ChromaDB (`collection.delete(where={"transcript_id": id})`).
  2. Only after that succeeds, delete (or soft-delete) the `transcript_metadata` row.
  If step 1 fails, step 2 is aborted and the row is flagged `ingestion_status = 'failed'` with a deletion error, so a cleanup job can retry — this guarantees PostgreSQL is never left pointing at vectors that no longer exist, and avoids orphaned vectors with no metadata record.

---

## 8. Example Records

**`sessions`**
```
id          : 8f14e45f-ceea-4b3f-8f9d-000000000001
title       : "Q3 Growth Strategy Brainstorm"
llm_provider: "anthropic"
llm_model   : "claude-sonnet-5"
status      : "active"
created_at  : 2026-07-28 14:02:11+00
updated_at  : 2026-07-30 09:15:44+00
metadata    : {"pinned": true, "tags": ["growth", "q3"]}
```

**`messages`**
```
id          : 1c3d2a90-3b3e-4f2b-9a2f-000000000010
session_id  : 8f14e45f-ceea-4b3f-8f9d-000000000001
role        : "user"
content     : "Summarize our onboarding funnel drop-off from the last transcript."
llm_provider: null
llm_model   : null
token_count : 18
created_at  : 2026-07-30 09:10:02+00
metadata    : {}
```
```
id          : 2d4e3ba1-4c4f-5a3c-ab30-000000000011
session_id  : 8f14e45f-ceea-4b3f-8f9d-000000000001
role        : "assistant"
content     : "Based on the ingested transcript, drop-off is highest at step 3..."
llm_provider: "anthropic"
llm_model   : "claude-sonnet-5"
token_count : 212
created_at  : 2026-07-30 09:10:09+00
metadata    : {"rag_used": true, "transcript_ids": ["6a1b2c3d-..."]}
```

**`artifacts`**
```
id            : 9e8d7c6b-5a4f-4321-9876-000000000020
message_id    : 2d4e3ba1-4c4f-5a3c-ab30-000000000011
session_id    : 8f14e45f-ceea-4b3f-8f9d-000000000001
artifact_type : "markdown"
title         : "Onboarding Funnel Drop-off Report"
content       : "# Onboarding Funnel Report\n\n## Step 3 Drop-off...\n"
version       : 1
created_at    : 2026-07-30 09:10:09+00
metadata      : {"artifact_key": "onboarding-funnel-report"}
```

**`transcript_metadata`**
```
id                     : 6a1b2c3d-4e5f-6789-abcd-000000000030
session_id             : 8f14e45f-ceea-4b3f-8f9d-000000000001
source_filename        : "user_interview_transcript_07.pdf"
source_type            : "pdf"
file_size_bytes        : 184320
chunk_count            : 42
embedding_model        : "text-embedding-3-large"
chroma_collection_name : "transcript_chunks"
ingestion_status       : "completed"
created_at             : 2026-07-29 18:44:00+00
updated_at             : 2026-07-29 18:44:52+00
metadata               : {"language": "en"}
```

**ChromaDB entry (illustrative, not a Postgres row)**
```
id       : "6a1b2c3d-4e5f-6789-abcd-000000000030__0007"
document : "Participants consistently abandoned onboarding at the payment step..."
embedding: [0.0123, -0.0456, ...]   (1536-dim vector)
metadata : {
  "transcript_id": "6a1b2c3d-4e5f-6789-abcd-000000000030",
  "session_id": "8f14e45f-ceea-4b3f-8f9d-000000000001",
  "chunk_index": 7,
  "source_filename": "user_interview_transcript_07.pdf",
  "created_at": "2026-07-29T18:44:30Z"
}
```

---

## 9. SQL Schema

```sql
-- ============================================================
-- Lenny Growth Assistant — PostgreSQL Schema
-- ============================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto"; -- for gen_random_uuid()

-- ------------------------------------------------------------
-- sessions
-- ------------------------------------------------------------
CREATE TABLE sessions (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title        VARCHAR(255) NOT NULL DEFAULT 'New Chat',
    llm_provider VARCHAR(50)  NOT NULL,
    llm_model    VARCHAR(100) NOT NULL,
    status       VARCHAR(20)  NOT NULL DEFAULT 'active'
                 CHECK (status IN ('active', 'archived', 'deleted')),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT now(),
    metadata     JSONB        NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_sessions_status     ON sessions (status);
CREATE INDEX idx_sessions_created_at ON sessions (created_at DESC);
CREATE INDEX idx_sessions_metadata_gin ON sessions USING GIN (metadata);

-- ------------------------------------------------------------
-- messages
-- ------------------------------------------------------------
CREATE TABLE messages (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role         VARCHAR(20) NOT NULL
                 CHECK (role IN ('user', 'assistant', 'system')),
    content      TEXT NOT NULL,
    llm_provider VARCHAR(50),
    llm_model    VARCHAR(100),
    token_count  INTEGER CHECK (token_count IS NULL OR token_count >= 0),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata     JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_messages_session_id      ON messages (session_id);
CREATE INDEX idx_messages_session_created ON messages (session_id, created_at);
CREATE INDEX idx_messages_role            ON messages (role);
CREATE INDEX idx_messages_metadata_gin    ON messages USING GIN (metadata);

-- ------------------------------------------------------------
-- artifacts
-- ------------------------------------------------------------
CREATE TABLE artifacts (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id    UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    session_id    UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    artifact_type VARCHAR(20) NOT NULL
                  CHECK (artifact_type IN ('html', 'markdown')),
    title         VARCHAR(255) NOT NULL DEFAULT 'Untitled Artifact',
    content       TEXT NOT NULL,
    version       INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata      JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_artifacts_message_id ON artifacts (message_id);
CREATE INDEX idx_artifacts_session_id ON artifacts (session_id);
CREATE INDEX idx_artifacts_type       ON artifacts (artifact_type);

-- ------------------------------------------------------------
-- transcript_metadata
-- ------------------------------------------------------------
CREATE TABLE transcript_metadata (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id              UUID REFERENCES sessions(id) ON DELETE SET NULL,
    source_filename         VARCHAR(500) NOT NULL,
    source_type             VARCHAR(50) NOT NULL
                            CHECK (source_type IN ('pdf', 'txt', 'md', 'docx', 'url', 'other')),
    file_size_bytes         BIGINT CHECK (file_size_bytes IS NULL OR file_size_bytes >= 0),
    chunk_count             INTEGER NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
    embedding_model         VARCHAR(100) NOT NULL,
    chroma_collection_name  VARCHAR(255) NOT NULL,
    ingestion_status        VARCHAR(20) NOT NULL DEFAULT 'pending'
                            CHECK (ingestion_status IN ('pending', 'processing', 'completed', 'failed')),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata                JSONB       NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX idx_transcript_session_id  ON transcript_metadata (session_id);
CREATE INDEX idx_transcript_status      ON transcript_metadata (ingestion_status);
CREATE INDEX idx_transcript_collection  ON transcript_metadata (chroma_collection_name);

-- ------------------------------------------------------------
-- updated_at maintenance trigger (shared)
-- ------------------------------------------------------------
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_sessions_updated_at
    BEFORE UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_transcript_updated_at
    BEFORE UPDATE ON transcript_metadata
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
```

---

## 10. Performance Considerations

- **Pagination:** All list endpoints (messages within a session, sessions list) use keyset pagination on indexed `(session_id, created_at)` / `created_at` columns rather than `OFFSET`, keeping response times flat regardless of table size.
- **Query optimization:** The composite index on `messages(session_id, created_at)` covers the dominant read pattern with a single index scan. `EXPLAIN ANALYZE` should be run against this query pattern before production launch and periodically as data grows to confirm the planner continues choosing the index scan over a sequential scan.
- **Connection pooling:** The application should never open raw connections per request. A pooler (PgBouncer in `transaction` mode, or the ORM's built-in pool) sized to `(max_concurrent_requests / avg_query_time)` prevents connection exhaustion under load; PostgreSQL's own `max_connections` should stay conservative (e.g., 100–200) with pooling absorbing burst concurrency.
- **Large conversations:** Sessions with very long histories (thousands of messages) rely on the same keyset-paginated index scan — cost stays roughly constant per page. If `content` payloads grow large (e.g., pasted logs), PostgreSQL's TOAST mechanism transparently compresses/out-of-lines large TEXT values, so no separate blob table is needed at this scale.
- **JSONB metadata:** GIN indexes on `metadata` columns are optional overhead — only created on tables where ad-hoc metadata filtering is an actual product requirement (all four tables here, since tagging/pinning/flags are expected features). If a table's metadata is write-only/audit-only, the GIN index should be dropped to save write overhead.
- **Vector search:** ChromaDB's HNSW index parameters (`ef_construction`, `M`) should be tuned once collection size and latency targets are known; this is independent of the PostgreSQL schema and does not block relational performance.

---

## 11. Security

- **SQL injection prevention:** All queries use parameterized statements via the ORM/driver (e.g., SQLAlchemy, asyncpg) — no string-concatenated SQL, anywhere, including dynamic `JSONB` filter construction (always pass filter values as bound parameters, never interpolate into the query string).
- **Input validation:** All user-supplied values (message content, session titles, uploaded filenames) are validated and length-checked at the application boundary (e.g., Pydantic models) before reaching the database; CHECK constraints in the schema are a second line of defense, not the primary one.
- **Sensitive data:** This schema does not currently store authentication credentials, PII beyond what a user chooses to paste into `content`, or payment data. `content` fields should be treated as potentially containing sensitive user-pasted material and excluded from verbose application logs.
- **Secrets:** Database credentials, LLM provider API keys, and embedding-model API keys are never stored in any table (including `metadata` JSONB columns) — they live in a secrets manager (e.g., environment variables backed by Vault/AWS Secrets Manager) and are referenced by name/role only, never persisted in application data.
- **Least privilege:** The application's database role should have `SELECT/INSERT/UPDATE/DELETE` on application tables only — no `SUPERUSER`, no `DROP`/`CREATE` privileges at runtime; schema migrations run under a separate, more privileged migration role.
- **Cascading deletes as a safety property:** `ON DELETE CASCADE` from `sessions` prevents orphaned `messages`/`artifacts` from silently accumulating and leaking data belonging to a "deleted" session.

---

## 12. Future Extensions

The schema is intentionally normalized and UUID-keyed so the following can be added without breaking existing tables:

- **Authentication / user accounts:** Add a `users` table (`id UUID PK`, `email`, `password_hash`, `created_at`, ...). Add `sessions.user_id UUID NOT NULL REFERENCES users(id)` (nullable initially for backfill, then tightened). All existing queries simply gain a `WHERE user_id = $1` filter.
- **Sharing conversations:** Add a `session_shares` table (`id`, `session_id FK`, `shared_with_user_id FK` or `share_token`, `permission` [`view`/`edit`], `created_at`, `expires_at`) — a pure join/junction table, no changes needed to `sessions`/`messages`.
- **Conversation folders:** Add a `folders` table (`id`, `user_id FK`, `name`, `parent_folder_id` self-FK for nesting, `created_at`) and `sessions.folder_id UUID NULL REFERENCES folders(id) ON DELETE SET NULL`.
- **Feedback:** Add a `message_feedback` table (`id`, `message_id FK`, `user_id FK`, `rating` [thumbs up/down or 1–5], `comment TEXT`, `created_at`) — 1:N from `messages`, fully additive.
- **Analytics:** Either (a) build materialized views/aggregation queries directly on `sessions`/`messages`/`artifacts` (token usage per provider, sessions per day), or (b) stream events to a separate analytics warehouse (e.g., via CDC/Debezium off the Postgres WAL) — the OLTP schema stays untouched either way.
- **Multi-tenancy (org/workspace):** Add `organizations` and `organization_members`, then `sessions.organization_id`, following the same additive-FK pattern as `users`.

None of these require altering the shape of `sessions`, `messages`, `artifacts`, or `transcript_metadata` beyond adding nullable foreign key columns — a deliberate design goal.

---

## 13. Design Decisions

| # | Decision | Alternative Considered | Reason |
|---|---|---|---|
| 1 | UUID primary keys (`gen_random_uuid()`) | Auto-incrementing `BIGSERIAL` | UUIDs are safe to generate client-side/pre-insert, avoid exposing row counts, and merge cleanly across environments (e.g., seed data, replicas) without collision. |
| 2 | Separate `artifacts` table vs. embedding artifact content in `messages` | Store artifact HTML/Markdown as a JSONB field on `messages` | Keeps `messages` lean for the hot "load conversation" path; artifacts have their own lifecycle (versioning, type-specific queries) that deserves a dedicated table. |
| 3 | `session_id` denormalized onto `artifacts` | Always join through `messages` to reach `session_id` | The "all artifacts in this session" query is common in the UI (artifact panel); avoiding a join keeps it a single indexed lookup. Trade-off: requires the two FKs to stay consistent (enforced at application layer / trigger). |
| 4 | ChromaDB stores only embeddings + minimal metadata, not full transcript metadata | Store all transcript metadata (status, size, filename) inside Chroma's metadata | Chroma metadata is not relationally queryable/joinable and has no ACID guarantees; keeping PostgreSQL authoritative means Chroma can be wiped and rebuilt at any time without data loss. |
| 5 | Logical (not FK-enforced) link between `transcript_metadata` and Chroma vectors | Attempt a "distributed foreign key" / two-phase commit across Postgres and Chroma | Cross-database FKs don't exist; a full 2PC is excessive complexity for this use case. A documented two-phase delete/write convention (§7.5) is simpler and sufficient. |
| 6 | Soft delete (`status = 'deleted'`) as the default session deletion path | Always hard-delete on user request | Soft delete is reversible, supports "trash/restore" UX, and avoids accidental data loss; hard delete remains available as a separate privileged operation for actual retention/GDPR-style purges. |
| 7 | JSONB `metadata` column on every table | Fully normalized columns for every conceivable attribute (e.g., `is_pinned`, `tags`, `language` as first-class columns) | Product requirements for metadata are still evolving; JSONB + GIN index gives flexible, indexable extensibility without constant migrations, while core queryable fields (status, type, role) remain first-class typed columns. |
| 8 | Keyset pagination over `OFFSET/LIMIT` | Traditional `OFFSET`-based pagination | `OFFSET` degrades linearly with page depth and is unstable under concurrent inserts; keyset pagination on an indexed timestamp column stays O(log n) and stable. |
| 9 | `token_count` stored per message rather than computed on read | Recompute token counts on demand via a tokenizer call | Token counts are cheap to capture from the LLM provider's response at write time and are needed repeatedly (cost dashboards, context-window management) — storing avoids redundant tokenizer calls. |
| 10 | Artifacts are append-only/versioned (new row per revision) | Update artifact content in place | Preserves full history of generated documents (useful for "revert to previous version" UX and auditability) at the cost of some storage — an acceptable trade-off given TEXT compresses well via TOAST. |
| 11 | One shared ChromaDB collection (`transcript_chunks`) by default, not one per session | Create a new Chroma collection per session | Chroma's per-collection overhead makes a collection-per-session pattern costly at scale with many short-lived sessions; a shared collection filtered by `session_id`/`transcript_id` metadata scales better and is the default, with per-session collections available as an opt-in for strict isolation needs. |
| 12 | `llm_provider`/`llm_model` stored per-message, not only per-session | Store the provider/model only once at the session level | Sessions may switch models mid-conversation (a stated feature: "Multiple LLM providers"); per-message tracking preserves an accurate historical record of which model produced which response. |

---
