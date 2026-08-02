# The Lenny Growth Assistant — REST API Design Specification

**Document:** `docs/api_design.md`
**Status:** Implementation-ready
**Audience:** Backend engineers, frontend engineers, reviewers
**Depends on:** PRD, System Architecture, Database Design
**Backend:** FastAPI · **DB:** PostgreSQL · **Vector Store:** ChromaDB · **Frontend:** React · **LLM Providers:** Claude, OpenAI, Ollama

---

## 1. API Overview

The Lenny Growth Assistant exposes a single REST API that mediates between the React frontend and four backend subsystems: a relational store (PostgreSQL) for sessions/messages/artifacts/config, a vector store (ChromaDB) for transcript retrieval, an LLM abstraction layer that routes to Claude/OpenAI/Ollama, and an artifact renderer for Markdown/HTML output.

Design philosophy:

- **Resource-oriented, not RPC-oriented.** Nouns (`sessions`, `messages`, `artifacts`, `transcripts`, `config`) are the primary API surface. The one deliberate exception is `POST /chat`, which is a *process* endpoint (it orchestrates retrieval, routing, and generation) rather than a CRUD operation on a single resource — this is called out explicitly in Section 6.
- **Predictable and boring.** Standard HTTP verbs, standard status codes, standard JSON envelopes. Anyone who has used a well-designed REST API should be able to guess the shape of an endpoint before reading its docs.
- **Provider-agnostic by design.** The API never leaks Claude-specific, OpenAI-specific, or Ollama-specific request/response shapes to the client. The frontend talks to one contract; the LLM abstraction layer inside the backend handles provider differences.
- **Stateless requests, stateful sessions.** Each HTTP request is self-contained (no server-side request state), but conversation state is explicitly persisted server-side in PostgreSQL and referenced by `session_id`. This keeps horizontal scaling simple and keeps the frontend "dumb" (it doesn't need to replay full history on every call).
- **Fail loud, fail structured.** Every error, from a bad request body to an upstream LLM outage, returns the same JSON error envelope (Section 10) so client-side error handling is uniform.
- **Streaming-ready from day one.** Even though the initial implementation may respond synchronously, every chat/artifact-generation endpoint is shaped so that adding SSE streaming later does not require a breaking contract change (Section 12).

---

## 2. Authentication

**For this assignment: no authentication is required.** All endpoints are open on the network the service runs on (e.g., localhost or an internal Docker network). This is an explicit, scoped decision for the current phase — not an oversight — and is documented here so it is revisited before any multi-user or public deployment.

### How authentication would be added later

The API is structured so auth can be layered in without reshaping existing endpoints:

1. **Transport:** Introduce an `Authorization: Bearer <token>` header on every request. FastAPI's dependency-injection system allows this to be added as a single reusable dependency (`get_current_user`) attached to routers, without touching individual endpoint logic.
2. **Identity model:** Add a `users` table; add a nullable `user_id` foreign key to `sessions`, `artifacts`, and `transcripts`. Existing rows created in the no-auth phase can be backfilled to a "system" user.
3. **AuthN mechanism options:**
   - API keys (simplest — good fit for a single-tenant internal tool).
   - JWT issued by a login endpoint (`POST /auth/login`) — good fit once multiple humans use the assistant.
   - OAuth2/OIDC via an identity provider (Google/GitHub/SSO) — good fit for team or public rollout.
4. **AuthZ model:** Once `user_id` exists, every session/artifact/transcript read or write is scoped with `WHERE user_id = :current_user`. This is a `WHERE`-clause change, not an endpoint redesign.
5. **Endpoint impact:** No URL paths change. No request/response schemas change except that responses would additionally include `owner_id`. This is why the API is designed without embedding "current user" assumptions into the URL structure (e.g., we use `/sessions/{id}`, not `/users/{user_id}/sessions/{id}`) — ownership is enforced by the auth layer, not baked into routing.

---

## 3. Base URL & Versioning

```
Base URL: /api/v1
```

All endpoints in this document are relative to this base, e.g., `POST /api/v1/chat`.

### Versioning strategy

- **URI-based major versioning** (`/api/v1`, `/api/v2`, …). This is chosen over header-based versioning (`Accept: application/vnd.lenny.v2+json`) because it is simpler to reason about, trivially cacheable, and visible in logs/browser tools — a good tradeoff for a small-to-mid-size internal tool.
- **Minor/patch changes are non-breaking and do not bump the version:** adding a new optional request field, adding a new response field, adding a new endpoint, adding a new enum value that clients are expected to ignore-if-unknown.
- **Breaking changes bump the major version:** removing/renaming a field, changing a field's type, changing status code semantics, changing default behavior.
- **Deprecation policy:** when `/v2` ships, `/v1` remains live and marked deprecated (via a `Deprecation` and `Sunset` response header) for a defined overlap window before removal, giving the frontend time to migrate.
- Internally, routers are namespaced by version (e.g., a `v1` router package) so `v1` and `v2` can run side-by-side sharing lower-level services (LLM router, RAG engine) without code duplication.

---

## 4. Endpoint Categories

| Category | Prefix | Purpose |
|---|---|---|
| Health | `/health` | Liveness/readiness for orchestration & monitoring |
| Sessions | `/sessions` | Create/list/rename/delete chat sessions |
| Chat | `/chat` | The core orchestration endpoint: send a message, get a reply |
| Messages | `/sessions/{id}/messages` | Read persisted conversation history |
| Artifacts | `/artifacts` | Read/delete generated Markdown/HTML/essay artifacts |
| Configuration | `/config` | Read/update active LLM provider & model settings |
| Transcript Management | `/transcripts` | Read-only listing/inspection of ingested transcripts (RAG corpus) |

---

## 5. Session Endpoints

A **session** represents one persistent conversation thread. All messages and artifacts belong to exactly one session.

### `GET /sessions`

**Purpose:** List all chat sessions, most recently active first — powers the sidebar/session switcher in the React UI.

**Request:**
Query parameters (all optional):

| Param | Type | Default | Notes |
|---|---|---|---|
| `limit` | int | 20 | 1–100 |
| `offset` | int | 0 | ≥ 0 |
| `archived` | bool | `false` | include archived sessions if `true` |

**Response `200 OK`:**
```json
{
  "data": [
    {
      "id": "sess_8f3a1c",
      "title": "Ship30 essay ideas for Q3",
      "created_at": "2026-07-28T09:12:00Z",
      "updated_at": "2026-07-30T14:02:11Z",
      "message_count": 14,
      "archived": false,
      "last_provider_used": "claude"
    }
  ],
  "pagination": {
    "limit": 20,
    "offset": 0,
    "total": 47
  }
}
```

**Validation:** `limit` clamped to [1,100]; invalid types → `422`.

**Status Codes:** `200` success. `422` invalid query params. `500` unexpected server error.

---

### `POST /sessions`

**Purpose:** Create a new, empty chat session.

**Request:**
```json
{
  "title": "Ship30 essay ideas for Q3"
}
```
`title` is optional — if omitted, the backend assigns a placeholder (`"New Session"`) that is typically renamed automatically after the first message (see Section 6).

**Response `201 Created`:**
```json
{
  "id": "sess_8f3a1c",
  "title": "New Session",
  "created_at": "2026-07-30T14:02:11Z",
  "updated_at": "2026-07-30T14:02:11Z",
  "message_count": 0,
  "archived": false,
  "last_provider_used": null
}
```
Response includes a `Location: /api/v1/sessions/sess_8f3a1c` header.

**Validation:** `title`, if present, must be a string, 1–200 characters after trimming.

**Status Codes:** `201` created. `422` validation failure (e.g., title too long). `500` server error.

---

### `GET /sessions/{id}`

**Purpose:** Fetch a single session's metadata (not its messages — see Section on Messages below).

**Request:** Path param `id` (string session identifier).

**Response `200 OK`:** same shape as a single item in the `GET /sessions` list.

**Validation:** `id` must match the session ID format (`sess_[a-z0-9]+`).

**Status Codes:** `200` found. `404` no session with that id. `422` malformed id format. `500` server error.

**Errors:**
```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "No session found with id 'sess_8f3a1c'.",
    "details": {}
  }
}
```

---

### `PATCH /sessions/{id}`

**Purpose:** Rename a session and/or toggle its archived state. Partial update semantics — only supplied fields change.

**Request:**
```json
{
  "title": "Ship30 essays — final drafts",
  "archived": true
}
```
Both fields optional; at least one must be present.

**Response `200 OK`:** updated session object (same shape as `GET /sessions/{id}`).

**Validation:**
- Body must not be empty (at least one of `title`/`archived`).
- `title` 1–200 chars if present.
- `archived` must be boolean if present.
- Unknown fields rejected (strict schema).

**Status Codes:** `200` updated. `400` empty body. `404` session not found. `422` invalid field values. `500` server error.

---

### `DELETE /sessions/{id}`

**Purpose:** Permanently delete a session, its messages, and any artifacts scoped to it (cascade delete, consistent with the DB design's foreign-key `ON DELETE CASCADE`).

**Request:** Path param `id`.

**Response `204 No Content`** on success (empty body).

**Validation:** `id` must exist.

**Status Codes:** `204` deleted. `404` session not found. `409` (reserved — e.g., if soft-delete/legal-hold rules are added later). `500` server error.

**Design note:** deletion is hard-delete by default; if audit retention is later required, this becomes a soft-delete (`deleted_at` timestamp) without changing the endpoint contract — callers still see `204` and the row disappears from all `GET` endpoints.

---

## 6. Chat Endpoint

### `POST /chat`

This is the **core orchestration endpoint** of the system. It is intentionally *not* modeled as `POST /sessions/{id}/messages` because sending a chat message is not a plain "create a row" operation — it triggers a multi-step pipeline (history load → RAG retrieval → agent routing → LLM call → persistence → optional artifact creation). Treating it as its own verb-like resource keeps that complexity explicit and out of the Sessions/Messages CRUD surface.

**Request schema:**
```json
{
  "session_id": "sess_8f3a1c",
  "message": "Turn my notes on cold outreach into a Ship30 essay.",
  "mode": "essay",
  "provider_override": null,
  "rag": {
    "enabled": true,
    "transcript_ids": null
  },
  "stream": false
}
```

| Field | Type | Required | Notes |
|---|---|---|---|
| `session_id` | string | yes | Must reference an existing session |
| `message` | string | yes | 1–8000 chars |
| `mode` | enum | no | `chat` (default) \| `essay` \| `qa` — hints agent routing |
| `provider_override` | enum \| null | no | `claude`\|`openai`\|`ollama` — overrides the configured default for this call only |
| `rag.enabled` | bool | no | default `true` |
| `rag.transcript_ids` | array\|null | no | restrict retrieval to specific transcripts |
| `stream` | bool | no | default `false` (see Section 12) |

**Response schema (`stream:false`):**
```json
{
  "message": {
    "id": "msg_2291",
    "session_id": "sess_8f3a1c",
    "role": "assistant",
    "content": "Here's a draft essay based on your cold-outreach notes...",
    "content_type": "markdown",
    "created_at": "2026-07-30T14:05:22Z"
  },
  "artifact": {
    "id": "art_77c1",
    "type": "essay",
    "render_format": "markdown"
  },
  "rag": {
    "used": true,
    "sources": [
      {"transcript_id": "tr_014", "chunk_id": "tr_014_c07", "score": 0.83}
    ]
  },
  "provider_used": "claude",
  "agent_route": "essay_writer"
}
```
`artifact` is `null` when the turn produces plain conversational reply with no artifact. `rag` is `null`/omitted when `rag.enabled` was `false`.

**Complete request flow:**

1. **Validate** `session_id` exists and `message` passes length/content checks (Section 11).
2. **Load session history:** the backend reads prior messages for `session_id` from PostgreSQL (ordered by `created_at`), not from the client — the client never has to resend history. A configurable window (e.g., last N messages or last N tokens) is loaded to build the LLM context.
3. **Agent routing:** a lightweight router (rule-based first, upgradeable to an LLM-based classifier later) inspects `mode` (if given) and/or the message content to decide the *task type*: general chat, transcript Q&A, or Ship30 essay generation. This determines which system prompt / prompt template and which downstream steps run.
4. **RAG retrieval (conditional):** if the route is `qa`/`essay` (or `rag.enabled` is true and routing decides retrieval helps), the backend embeds the query and queries ChromaDB for the top-k relevant transcript chunks, optionally filtered to `rag.transcript_ids`. Retrieved chunks are injected into the prompt as context, and their identifiers are returned in `rag.sources` for traceability.
5. **LLM provider selection:** the backend resolves which provider/model to call by checking, in order: (a) `provider_override` on this request, (b) the session's last-used provider if "sticky" behavior is configured, (c) the global default from `GET /config`. This resolution happens entirely server-side inside the LLM abstraction layer — the client only ever sees the resulting `provider_used`.
6. **Generation:** the resolved provider's adapter is called with the assembled prompt (system prompt + routed instructions + RAG context + trimmed history + new message).
7. **Post-processing:** if the route is `essay` (or the model output is detected as a renderable artifact — e.g., fenced HTML/Markdown block above a size threshold), the content is persisted as a row in `artifacts` and rendered per Section 7; the chat message itself stores a reference to `artifact_id`.
8. **Persistence:** both the user's message and the assistant's reply are written to `messages`; `sessions.updated_at` (and `title`, if this was the first message and no title was set) are updated in the same transaction.
9. **Response:** the assistant message, optional artifact summary, RAG source list, and resolved provider are returned to the client.

**Validation:** see Section 11.

**Status Codes:** `200` success. `400` malformed body. `404` `session_id` not found. `422` field-level validation failure (e.g., message too long, invalid `mode`/`provider_override` enum). `502` upstream LLM provider returned an error. `503` upstream LLM provider unreachable/timed out. `500` internal error (e.g., DB write failure after generation succeeded — see error handling note below).

**Error handling note:** generation and persistence are treated as a single logical operation. If the LLM call succeeds but the DB write fails, the API returns `500` and does **not** silently drop the reply — the response error includes enough detail (or a retry token) for the client to avoid double-charging an LLM call on retry; this is called out as a design decision in Section 16.

---

## 7. Artifact Endpoints

An **artifact** is a generated deliverable — a Ship30 essay, a Markdown document, or an HTML snippet — produced by a chat turn and stored independently so it can be fetched, re-rendered, or deleted without replaying the conversation.

### `GET /artifacts/{id}`

**Purpose:** Fetch a single artifact's content and rendering metadata.

**Response `200 OK`:**
```json
{
  "id": "art_77c1",
  "session_id": "sess_8f3a1c",
  "type": "essay",
  "render_format": "markdown",
  "title": "Why Cold Outreach Still Works in 2026",
  "content": "# Why Cold Outreach Still Works\n\n...",
  "created_at": "2026-07-30T14:05:22Z",
  "updated_at": "2026-07-30T14:05:22Z"
}
```

`render_format` is one of `markdown` | `html`. For `html`, `content` is sanitized server-side before storage (see rendering workflow below) — the API never returns raw, unsanitized HTML.

**Validation:** `id` must match artifact ID format.

**Status Codes:** `200` found. `404` not found. `500` server error.

---

### `DELETE /artifacts/{id}`

**Purpose:** Permanently delete an artifact. The originating chat message is retained but its `artifact_id` reference becomes null (message text stays intact; only the rendered deliverable is removed).

**Response:** `204 No Content`.

**Status Codes:** `204` deleted. `404` not found. `500` server error.

### Rendering workflow

1. **Generation:** the LLM's raw output for an essay/artifact turn is captured as plain text (Markdown or HTML per the task).
2. **Classification:** the post-processing step in `POST /chat` (Section 6, step 7) tags the artifact's `render_format` based on the agent route (`essay_writer` → `markdown`) or on detected content shape (fenced ` ```html ` block → `html`).
3. **Sanitization (HTML only):** before persisting, HTML content is passed through a server-side sanitizer (allow-listed tags/attributes, scripts stripped) so that whatever the React frontend renders (e.g., in a sandboxed `<iframe>` or via a sanitized-HTML React component) cannot execute arbitrary script from the model output.
4. **Persistence:** the sanitized/raw content, `type`, and `render_format` are written to the `artifacts` table, linked to the originating `session_id` and `message_id`.
5. **Client rendering:** the React frontend fetches via `GET /artifacts/{id}` and renders `markdown` content with a Markdown renderer (e.g., `react-markdown`) or `html` content inside a sandboxed container. The API's job ends at "return safe, classified content" — actual rendering is a frontend concern.

---

## 8. Configuration Endpoint

### `GET /config`

**Purpose:** Return the current active LLM provider/model and any tunable generation parameters.

**Response `200 OK`:**
```json
{
  "active_provider": "claude",
  "providers": {
    "claude": {
      "model": "claude-sonnet-5",
      "available": true,
      "temperature": 0.7
    },
    "openai": {
      "model": "gpt-4.1",
      "available": true,
      "temperature": 0.7
    },
    "ollama": {
      "model": "llama3.1:8b",
      "available": false,
      "temperature": 0.7
    }
  },
  "rag_default_enabled": true,
  "updated_at": "2026-07-29T10:00:00Z"
}
```
`available` reflects a lightweight health/connectivity check (e.g., Ollama's local endpoint unreachable) rather than the provider's global status.

### `PATCH /config`

**Purpose:** Change the active provider and/or per-provider settings.

**Request:**
```json
{
  "active_provider": "openai",
  "providers": {
    "openai": {
      "model": "gpt-4.1",
      "temperature": 0.5
    }
  }
}
```
Partial update: only supplied provider entries are changed; others are untouched.

**Response `200 OK`:** the full updated config object (same shape as `GET /config`).

**Validation:**
- `active_provider`, if present, must be one of `claude`|`openai`|`ollama`.
- `temperature` in `[0.0, 1.0]` (or provider-appropriate range).
- `model` must be a non-empty string; the backend does *not* hard-validate against a live provider model list at this layer (that would couple config validation to network calls) — invalid/unsupported model names surface as a `502` from the provider adapter on the next `/chat` call, with a clear error message.

**Status Codes:** `200` updated. `422` invalid field values (e.g., unknown `active_provider` enum, out-of-range temperature). `500` server error.

### Provider switching explained

- Configuration is a single row (or small table) in PostgreSQL, read on every `/chat` call (with in-process caching + invalidation on `PATCH /config` to avoid a DB round-trip per chat request).
- The LLM abstraction layer defines one adapter interface (`generate(messages, system_prompt, **params) -> AssistantReply`) implemented once per provider (Claude, OpenAI, Ollama). `POST /chat` never branches on provider name outside this layer — it just asks the layer for "the currently configured provider's adapter" (or the `provider_override` adapter, if given per-request).
- Switching providers via `PATCH /config` takes effect on the *next* `/chat` call; it does not retroactively change how past messages were generated (each stored message already recorded which provider produced it — see `last_provider_used` in Section 5 and `provider_used` in Section 6).
- Ollama's `available: false` case: if a user switches `active_provider` to `ollama` while the local Ollama server is down, `PATCH /config` still succeeds (config is a stated preference, not a live capability check) but the next `POST /chat` call fails with `503` and a clear `PROVIDER_UNAVAILABLE` error — this separation keeps configuration changes fast and side-effect-free.

---

## 9. Transcript Endpoints

Transcripts are the RAG corpus (e.g., podcast/interview transcripts) that back transcript Q&A and essay generation.

### `GET /transcripts`

**Purpose:** List ingested transcripts available for retrieval — powers a "sources" picker in the UI and the `rag.transcript_ids` filter in `POST /chat`.

**Request:** Query params `limit`, `offset` (same semantics as Section 5).

**Response `200 OK`:**
```json
{
  "data": [
    {
      "id": "tr_014",
      "title": "Lenny's Podcast — Growth Loops Deep Dive",
      "source_url": "https://example.com/episode-42",
      "ingested_at": "2026-06-01T08:00:00Z",
      "chunk_count": 212
    }
  ],
  "pagination": {"limit": 20, "offset": 0, "total": 63}
}
```

**Status Codes:** `200` success. `422` bad query params. `500` server error.

### `GET /transcripts/{id}`

**Purpose:** Fetch a single transcript's metadata (not full chunk-level content — that lives in ChromaDB and is retrieved implicitly during RAG, not browsed directly via this API).

**Response `200 OK`:** same shape as a single list item, plus optionally a `summary` field if one was generated at ingestion time.

**Status Codes:** `200` found. `404` not found. `500` server error.

### Why ingestion is an offline script, not a public endpoint

Transcript ingestion (chunking, embedding, writing to ChromaDB + a `transcripts` metadata row in PostgreSQL) is intentionally **excluded** from the public API surface:

1. **Heavy, slow, and bursty.** Ingesting a transcript involves chunking, calling an embedding model potentially hundreds of times, and writing to two stores. This doesn't fit the request/response latency profile of a REST endpoint without adding a job queue — solvable, but unnecessary complexity for an admin-only, low-frequency task.
2. **No untrusted input path needed.** Transcripts are curated content added by the team/admin, not end-user-submitted data. Exposing `POST /transcripts` would require upload handling, format validation, and abuse controls for a use case that, per the PRD, doesn't need multi-user self-serve ingestion.
3. **Operational simplicity.** A CLI/offline script (run manually or via a scheduled job) that talks directly to PostgreSQL and ChromaDB is easier to reason about, easier to re-run idempotently, and keeps the API's blast radius smaller — a bug in the API can't accidentally corrupt the RAG corpus.
4. **Read-only API surface is sufficient** for everything the product actually needs from the frontend: listing what's available and letting `POST /chat` reference it.

If self-serve ingestion becomes a real requirement later, it is added as `POST /transcripts` returning `202 Accepted` with a background job id — an additive, non-breaking change.

---

## 10. Error Responses

All errors share one envelope:

```json
{
  "error": {
    "code": "MACHINE_READABLE_CODE",
    "message": "Human-readable explanation.",
    "details": {}
  }
}
```

`details` is an optional object for field-level or context-specific info (e.g., validation failures per field).

### `400 Bad Request` — malformed request (e.g., invalid JSON, empty PATCH body)
```json
{
  "error": {
    "code": "BAD_REQUEST",
    "message": "Request body must contain at least one field to update.",
    "details": {}
  }
}
```

### `404 Not Found` — referenced resource doesn't exist
```json
{
  "error": {
    "code": "SESSION_NOT_FOUND",
    "message": "No session found with id 'sess_8f3a1c'.",
    "details": {"session_id": "sess_8f3a1c"}
  }
}
```

### `422 Unprocessable Entity` — schema/field-level validation failure
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more fields failed validation.",
    "details": {
      "message": "must be between 1 and 8000 characters",
      "provider_override": "must be one of: claude, openai, ollama"
    }
  }
}
```

### `500 Internal Server Error` — unhandled server-side failure
```json
{
  "error": {
    "code": "INTERNAL_ERROR",
    "message": "An unexpected error occurred. Please try again.",
    "details": {}
  }
}
```

### `503 Service Unavailable` — upstream dependency (LLM provider, ChromaDB) down
```json
{
  "error": {
    "code": "PROVIDER_UNAVAILABLE",
    "message": "The configured provider 'ollama' is unreachable. Check that the local Ollama server is running.",
    "details": {"provider": "ollama"}
  }
}
```

---

## 11. Validation

Validation happens in two layers: FastAPI/Pydantic schema validation (structural, type-level — surfaces as `422`) and business-rule validation (existence/consistency checks — surfaces as `404`/`409`/`400` depending on the case).

| Concern | Rule |
|---|---|
| Message length | `message` in `POST /chat`: 1–8000 characters (trimmed); empty or whitespace-only rejected |
| Session title length | 1–200 characters |
| Session existence | Any endpoint referencing `session_id` verifies the row exists before proceeding; missing → `404` |
| Provider validation | `provider_override` / `active_provider` restricted to the enum `claude`\|`openai`\|`ollama`; unknown value → `422`. Live reachability is checked lazily at call time, not at validation time (see Section 8), surfacing as `503` rather than `422` |
| Artifact validation | `render_format` restricted to `markdown`\|`html`; HTML content is sanitized server-side before persistence (Section 7); artifact `type` restricted to a known enum (`essay`, `markdown_doc`, `html_snippet`, …) |
| Pagination params | `limit` clamped/validated to `[1,100]`; `offset` must be `≥ 0` |
| ID formats | Path-parameter IDs are validated against their expected prefix pattern (`sess_`, `msg_`, `art_`, `tr_`) before a DB lookup is attempted, so malformed IDs fail fast as `422` rather than falling through to a `404` |
| RAG scoping | If `rag.transcript_ids` is provided, each ID is checked against existing transcripts; unknown IDs → `422` with the offending IDs listed in `details` |

---

## 12. Streaming Strategy

The initial implementation of `POST /chat` returns a single synchronous JSON response (`stream: false`, Section 6). The contract is designed so streaming can be added without a breaking change:

- **Trigger:** the same `POST /chat` endpoint accepts `"stream": true` in the request body. No new endpoint or URL is introduced.
- **Transport:** when `stream: true`, the response `Content-Type` becomes `text/event-stream` (Server-Sent Events) instead of `application/json`. SSE is chosen over WebSockets because chat responses are one-directional (server → client) for the duration of a single turn, and SSE works over plain HTTP, simplifying infra (works through standard reverse proxies/load balancers, no separate socket protocol).
- **Event shape:** each SSE event carries an incremental JSON payload, e.g.:
  ```
  event: token
  data: {"delta": "Here's a draft "}

  event: token
  data: {"delta": "essay based on..."}

  event: done
  data: {"message": {...same final shape as the non-streaming response...}, "artifact": {...}, "rag": {...}, "provider_used": "claude"}
  ```
- **Backward compatibility:** clients that don't send `stream: true` are entirely unaffected. Clients that do must switch their HTTP client to an SSE-capable reader (e.g., `EventSource` or a fetch-based SSE parser) — a frontend-side change, not an API contract break.
- **Persistence timing:** the full assistant message is still persisted once generation completes (on the `done` event), identical to the non-streaming flow — streaming only changes *delivery*, not the underlying orchestration steps from Section 6.
- **Provider support:** all three providers (Claude, OpenAI, Ollama) support token-streaming natively; the LLM abstraction layer's adapter interface is defined with both a `generate()` and a `stream()` method from the start, even though only `generate()` is wired to the endpoint initially, so enabling streaming later is a routing change, not an adapter rewrite.

---

## 13. Sequence Diagrams

### Creating a new chat session

```
React Frontend        FastAPI /sessions        PostgreSQL
      |                       |                      |
      |--POST /sessions------>|                      |
      |                       |--INSERT session----->|
      |                       |<--row created---------|
      |<--201 Created---------|                      |
      |  {id, title, ...}     |                      |
```

### Sending a message (POST /chat, non-streaming)

```
React Frontend      FastAPI /chat      PostgreSQL      ChromaDB      LLM Provider
      |                   |                 |              |              |
      |--POST /chat------>|                 |              |              |
      |                   |--load history-->|              |              |
      |                   |<--messages------|              |              |
      |                   |--agent routing (in-process)--- |              |
      |                   |--embed + query------------------------------>|
      |                   |                 |              |              |
      |                   |<--top-k chunks-------------------------------|
      |                   |--select provider (config lookup)             |
      |                   |--generate(prompt+context)------------------->|
      |                   |<--assistant reply-----------------------------|
      |                   |--persist user+assistant msgs->|              |
      |                   |--persist artifact (if any)--->|              |
      |<--200 OK----------|                 |              |              |
      | {message, artifact,rag,provider}    |              |              |
```

### Generating an artifact (as part of a chat turn)

```
FastAPI /chat        Post-processing        Sanitizer        PostgreSQL
      |                     |                    |                |
      |--LLM output-------->|                    |                |
      |                     |--classify format-->|                |
      |                     |  (markdown/html)   |                |
      |                     |--if html: sanitize->|                |
      |                     |<--sanitized html----|                |
      |                     |--INSERT artifacts row--------------->|
      |                     |<--artifact id-------------------------|
      |<--artifact summary--|                    |                |
```

### Switching LLM providers

```
React Frontend      FastAPI /config      PostgreSQL      (next turn) FastAPI /chat
      |                    |                   |                        |
      |--PATCH /config---->|                   |                        |
      | {active_provider:  |                   |                        |
      |   "openai"}        |--UPDATE config--->|                        |
      |                    |<--row updated------|                        |
      |<--200 OK-----------|                   |                        |
      | {active_provider:  |                   |                        |
      |   "openai", ...}   |                   |                        |
      |                                         |                        |
      |--POST /chat (no provider_override)---------------------------->|
      |                                         |  reads config: openai |
      |<---------------------------------------------response uses openai
```

---

## 14. API Versioning (Future Compatibility)

- Current and only version: `v1`. All contracts in this document are `v1`.
- **Additive changes** (new optional fields, new endpoints, new enum values clients should ignore-if-unrecognized) ship within `v1` — no version bump required. Clients are expected to ignore unknown response fields rather than fail on them (a documented client-side contract).
- **Breaking changes** (field removal/rename, type change, changed status-code meaning, changed default behavior) require a `v2` namespace. `v1` and `v2` routers can coexist behind the same FastAPI app, sharing services (LLM router, RAG engine, DB session) so the cost of maintaining both is mostly router/schema duplication, not business logic duplication.
- **Provider additions** (e.g., adding a fourth LLM provider) are additive: a new enum value for `active_provider`/`provider_override`, plus a new adapter implementation behind the existing interface — not a version bump.
- **Deprecation signaling:** deprecated versions/endpoints return a `Deprecation: true` header and, once a sunset date is set, a `Sunset: <date>` header, giving consumers a machine-readable migration signal ahead of removal.

---

## 15. OpenAPI / Swagger

FastAPI generates an OpenAPI 3.x schema automatically from the route definitions, Pydantic models, and docstrings/`Field(..., description=...)` metadata used in the implementation — no separate spec file needs to be hand-maintained.

- **Interactive docs:** available at `/docs` (Swagger UI) and `/redoc` (ReDoc) by default, served by FastAPI without extra configuration.
- **Raw schema:** available at `/openapi.json`, which can be fed into client-code generators (e.g., `openapi-typescript`) so the React frontend can derive typed API clients directly from the backend's schema instead of hand-writing request/response types — keeping frontend and backend contracts in sync automatically.
- **Documentation fidelity:** every request/response model, field constraint (min/max length, enum values), and status code documented in this specification maps directly to a Pydantic model, `Field(...)` constraint, and `responses={...}` declaration in the implementation, so `/docs` stays a faithful, always-current mirror of this document rather than a separate artifact that can drift.
- **Versioned docs:** once `v2` exists, FastAPI can serve separate `/docs` instances per version (e.g., mounted as sub-applications), so `v1` and `v2` consumers each see only their relevant contract.

---

## 16. Design Decisions

| # | Decision | Alternative Considered | Reason |
|---|---|---|---|
| 1 | `POST /chat` as one orchestration endpoint | Separate endpoints per step: `POST /rag/query`, `POST /messages`, `POST /artifacts/generate` | A chat turn is one atomic unit of work from the client's perspective; splitting it would push orchestration (and its failure handling) into the frontend, duplicating logic the backend is better positioned to own |
| 2 | URI-based versioning (`/api/v1`) | Header-based versioning (`Accept: vnd...+json`) | Simpler to route, cache, log, and debug; adequate for this project's scale and consumer count (one frontend) |
| 3 | No auth for v1, auth added via dependency injection later | Build auth scaffolding now even though unused | YAGNI for the current scope; FastAPI's dependency system makes retrofitting low-cost, so paying that cost upfront isn't justified |
| 4 | Hard-delete on `DELETE /sessions/{id}` (cascade) | Soft-delete with `deleted_at` | Simpler mental model and matches the current requirement (no audit/retention need yet); trivially upgradable later without an endpoint contract change |
| 5 | Ingestion as an offline script, not an API endpoint | `POST /transcripts` accepting raw files | Ingestion is slow, admin-only, and low-frequency; keeping it out of the API reduces blast radius and avoids building async job infrastructure prematurely |
| 6 | SSE for streaming (future) | WebSockets | Chat responses are unidirectional per turn; SSE works over plain HTTP/existing proxies without a new protocol, and providers already emit token streams SSE can relay directly |
| 7 | Provider selection resolved server-side in `/chat`, never exposed as provider-specific request/response shapes | Let the frontend call provider-specific endpoints (`/chat/claude`, `/chat/openai`) | Keeps the frontend contract stable across provider changes/additions; all provider quirks are isolated to one abstraction layer |
| 8 | Uniform error envelope (`error.code`/`message`/`details`) across all endpoints | Per-endpoint bespoke error shapes | One error-handling code path on the frontend; machine-readable `code` supports programmatic handling (e.g., retry on `PROVIDER_UNAVAILABLE`) without string-matching `message` |
| 9 | Config stores "preference," reachability checked lazily at call time | Validate provider reachability synchronously inside `PATCH /config` | Keeps config updates fast and side-effect-free; avoids a confusing state where a config change fails because of a transient network blip unrelated to the setting itself |
| 10 | Artifacts stored as their own resource/table, referenced by messages | Store generated Markdown/HTML inline in the `messages` row | Lets artifacts be fetched, deleted, or re-rendered independently of the conversation, and keeps `messages` rows lean for history-loading performance |
| 11 | HTML artifacts sanitized server-side before persistence | Sanitize only at render time in the frontend | Defense in depth: guarantees no unsanitized model-generated HTML is ever stored or served, even if a future client forgets to sanitize on render |
| 12 | Pagination via `limit`/`offset` | Cursor-based pagination | Simpler to implement and sufficient at this data scale (sessions/transcripts numbering in the hundreds–thousands); revisit if lists grow large enough for offset-scan cost to matter |

---

*End of `docs/api_design.md`.*
