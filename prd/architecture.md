# The Lenny Growth Assistant — Architecture Design Document

**Document status:** Final for implementation
**Audience:** Engineering team, technical reviewers
**Scope:** End-to-end system architecture prior to implementation

---

## 1. Executive Summary

The Lenny Growth Assistant is a conversational AI application built on top of Lenny's Podcast transcripts. It combines Retrieval-Augmented Generation (RAG), a lightweight agent router, and three purpose-built AI Skills (Transcript Q&A, Ship30for30 Essay Generation, and Artifact Generation) to give users a single chat interface that can answer questions grounded in podcast content, draft short-form essays in a specific style, and produce renderable HTML/CSS artifacts.

The system is a classic three-tier application with an AI-specific middle layer:

- **Frontend (React):** chat interface, session sidebar, and an artifact viewer, all talking to the backend over a REST API.
- **Backend (FastAPI):** a layered service that exposes chat and session endpoints, delegates business logic to services, routes requests to the correct Skill, and abstracts the underlying LLM provider.
- **Data layer:** PostgreSQL for session/message persistence, ChromaDB for vector storage of transcript chunks.

The architecture deliberately avoids enterprise machinery (message queues, microservices, container orchestration) that would be disproportionate to the assignment's scope. Instead, it invests in clean layering, a provider-agnostic LLM interface, and a rule-based router — all of which are cheap to build now and cheap to extend later. Every major axis of future growth (auth, streaming, more skills, more providers, cloud deployment) is designed for via interfaces and configuration, not by pre-building the feature itself.

---

## 2. Architecture Principles

**Modular Design**
Each concern — API routing, business logic, skill execution, prompt construction, LLM invocation, persistence — lives in its own module with a narrow, well-documented interface. Modules are composed, not entangled: the Agent Router doesn't know how a Skill builds its prompt, and a Skill doesn't know which LLM provider is configured.

**Loose Coupling**
Components communicate through interfaces and data contracts (Pydantic models), never through shared mutable state or direct imports of internal implementation details. The `LLMProvider` interface is the clearest example: skills call `provider.generate(...)` and are indifferent to whether that resolves to Claude, OpenAI, or Ollama.

**Configuration over Hardcoding**
Provider selection, model names, chunking parameters, database URLs, and feature flags all live in environment variables and a central `Settings` object (Pydantic `BaseSettings`). Switching from Claude to Ollama, or changing the embedding model, is a config change — never a code change.

**Single Responsibility**
Every class and module answers one question. `SessionService` manages sessions. `RetrievalService` manages vector search. `AgentRouter` decides *which* skill runs. Each `Skill` decides *how* to answer once selected. This keeps each unit small enough to unit-test in isolation and to reason about during code review.

**Extensibility**
New Skills, new LLM providers, and new artifact types are additive, not invasive. Adding a provider means implementing one interface and registering it in a factory. Adding a skill means implementing one interface and adding a routing rule. No existing code needs to change shape to accommodate growth — only to register the new component.

---

## 3. High-Level Architecture Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                          FRONTEND (React)                       │
│   Chat UI · Session Sidebar · Markdown Renderer · Artifact View │
└───────────────────────────────┬──────────────────────────────── ┘
                                 │  REST / JSON (HTTPS)
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                        FASTAPI (API Layer)                      │
│     /chat  /sessions  /messages  /health   (routers + schemas)  │
└───────────────────────────────┬──────────────────────────────── ┘
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                             SERVICES                            │
│   SessionService · MessageService · RetrievalService            │
│   (business logic, orchestration, persistence coordination)     │
└───────────────────────────────┬──────────────────────────────── ┘
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                          AGENT ROUTER                           │
│   Rule-based keyword/intent classifier → selects one Skill      │
└───────────────────────────────┬──────────────────────────────── ┘
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                              SKILLS                              │
│      QASkill        EssaySkill        ArtifactSkill             │
└───────────────────────────────┬──────────────────────────────── ┘
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                        PROMPT TEMPLATES                         │
│      Jinja2 / f-string templates per skill, versioned            │
└───────────────────────────────┬──────────────────────────────── ┘
                                 ▼
┌────────────────────────────────────────────────────────────────┐
│                    LLM PROVIDER (abstraction)                   │
│         ClaudeProvider · OpenAIProvider · OllamaProvider         │
└──────────────────┬─────────────────────────────┬────────────────┘
                    ▼                             ▼
        ┌────────────────────┐        ┌────────────────────────┐
        │     PostgreSQL      │        │        ChromaDB          │
        │ Sessions / Messages │        │  Transcript embeddings   │
        └────────────────────┘        └────────────────────────┘
```

Data flows top-to-bottom for a request, and the two data stores sit as siblings at the bottom: PostgreSQL is written to by the Services layer for session/message persistence, while ChromaDB is queried by the RetrievalService (invoked from the QASkill) and populated ahead of time by an offline ingestion pipeline.

---

## 4. Frontend Architecture

**Structure**

```
frontend/
  src/
    api/            # thin fetch wrappers around the FastAPI REST endpoints
    components/
      chat/         # MessageList, MessageBubble, ChatInput
      sidebar/      # SessionList, NewChatButton
      artifact/      # ArtifactViewer, ArtifactSandbox
      markdown/      # MarkdownRenderer (code blocks, tables, etc.)
    hooks/          # useSessions, useChat, useArtifact
    state/          # lightweight global store (Context + reducer, or Zustand)
    pages/          # ChatPage (composition root)
```

**Chat UI**
A `ChatPage` composes `Sidebar` + `MessageList` + `ChatInput`. Messages render through a single `MarkdownRenderer` component so that Q&A answers, essays, and artifact-announcement messages all share consistent typography, code highlighting, and link handling.

**Sidebar**
Lists sessions (title, last-updated timestamp) fetched via `GET /sessions`, supports creating a new session and switching between sessions. The active session ID is the single source of truth driving which conversation is loaded.

**Artifact Viewer**
When a message contains an artifact payload (HTML/CSS content plus metadata), the `ArtifactViewer` renders it in a separate panel using a **sandboxed iframe** (see §11), keeping generated HTML/CSS visually isolated from the host application's DOM and styles.

**State Management**
A minimal global store holds: `sessions[]`, `activeSessionId`, `messages[]`, `isStreamingOrLoading`, `activeArtifact`. React Query (or SWR) is used for server-state caching/fetching of sessions and message history, avoiding hand-rolled cache invalidation logic. Local component state is used for ephemeral UI (input box value, sidebar collapse).

**API Communication**
All backend calls go through a small `api/client.ts` wrapper that centralizes the base URL, error handling, and JSON parsing. The frontend never talks to Postgres or ChromaDB directly — it only speaks REST/JSON to FastAPI. This keeps the frontend fully decoupled from backend storage choices.

---

## 5. Backend Architecture

```
API Layer  →  Services  →  Skills  →  Provider Layer  →  Database
```

**API Layer (`app/api/`)**
FastAPI routers (`chat.py`, `sessions.py`, `health.py`). Responsible only for HTTP concerns: request validation (Pydantic models), status codes, and delegating to services. No business logic lives here.

**Services (`app/services/`)**
- `SessionService`: create/list/rename/delete sessions.
- `MessageService`: append messages to a session, load conversation history, persist Skill output.
- `RetrievalService`: embeds a query and performs similarity search against ChromaDB, returning ranked transcript chunks with source metadata (episode, guest, timestamp).

Services orchestrate calls to the database and to the Agent Router; they contain the application's business rules and are the layer most heavily unit-tested.

**Skills (`app/skills/`)**
Each Skill implements a common `Skill` interface (`run(context) -> SkillResult`). A Skill is responsible for building its prompt (via templates), invoking the LLM Provider, and post-processing the raw response into a structured result (plain answer, essay text, or artifact payload).

**Provider Layer (`app/providers/`)**
Implements the `LLMProvider` interface for Claude, OpenAI, and Ollama (see §9). This is the only layer that knows about vendor-specific SDKs, auth, and request/response shapes.

**Database (`app/db/`)**
SQLAlchemy models and repository-style access functions for PostgreSQL (`Session`, `Message`), plus a thin `VectorStore` wrapper around the ChromaDB client. Repositories are the only code that issues SQL/vector queries — services never construct queries directly.

Each layer only calls downward, never upward or sideways across layers, which keeps the dependency graph a simple directed line and makes each layer independently testable with the layer below mocked.

---

## 6. AI Architecture

**Transcript Ingestion**
An offline/one-time ingestion script reads raw transcript files (per-episode text/JSON), normalizes formatting (speaker labels, timestamps), and produces clean documents tagged with metadata (`episode_id`, `title`, `guest`, `published_date`).

**Chunking**
Transcripts are split into overlapping chunks (e.g., ~500–800 tokens with ~15% overlap), chunked on natural boundaries (speaker turns / paragraph breaks) rather than fixed character counts, to avoid splitting a coherent thought across chunks. Each chunk retains its source metadata for citation.

**Embedding**
Each chunk is embedded using a configurable embedding model (default: the embedding model matching the active LLM provider family, e.g., OpenAI `text-embedding-3-small`, with a local sentence-transformers model as the Ollama-compatible fallback). Embedding is a pluggable function so the embedding backend can change independently of the chat LLM provider.

**Vector Storage**
Embeddings + metadata are stored in a ChromaDB collection (`transcripts`), persisted to disk. Each document ID maps back to `(episode_id, chunk_index)` for traceability.

**Retrieval**
At query time, `RetrievalService` embeds the user's question with the same embedding model, performs a top-k similarity search (k configurable, default 5), and applies a lightweight relevance-score threshold to drop weak matches rather than always forcing k results into the prompt.

**Prompt Construction**
The `QASkill` fills a prompt template with: the user's question, the conversation history (trimmed to a token budget), and the retrieved chunks (with episode/guest citations). Templates are versioned text files, not inline strings, so prompt iteration doesn't require touching business logic.

**Response Generation**
The assembled prompt is sent to the configured `LLMProvider`. The response is returned as plain text (or, for the Artifact Skill, as text containing an embedded HTML block).

**Artifact Detection**
The `ArtifactSkill`'s prompt instructs the model to wrap generated HTML/CSS in a delimited block (e.g., a fenced ```html block or a `<artifact>` tag). After generation, a small parser extracts that block; if extraction fails, the system falls back to treating the response as plain markdown text (see §12, Malformed Artifacts) rather than failing the request.

---

## 7. Agent Router

The router's job is narrow and deliberately simple: given a user message (and light conversation context), decide **which single Skill** should handle it. Per the design goal of avoiding unnecessary complexity, this is **rule-based keyword/pattern matching**, not an LLM classification call — it's cheaper, deterministic, faster, and easy to unit test.

**Routing signals**

| Skill | Trigger examples |
|---|---|
| Artifact | "create a...", "build a...", "generate a landing page/dashboard/UI/component", "make an artifact", explicit mentions of HTML/webpage/UI |
| Essay | "write an essay", "ship30for30", "draft a post about...", "write a short post" |
| Q&A (default) | Everything else — questions, "what did X say about...", "summarize...", general chat |

**Routing flow**

```
user message
   │
   ▼
normalize text (lowercase, strip)
   │
   ▼
check Artifact keyword patterns  ──▶ match? ──▶ ArtifactSkill
   │ no match
   ▼
check Essay keyword patterns     ──▶ match? ──▶ EssaySkill
   │ no match
   ▼
default                                    ──▶ QASkill
```

The router is implemented as a single pure function (`route(message: str) -> SkillType`) with an ordered list of `(pattern, SkillType)` rules, checked most-specific-first (Artifact and Essay before the Q&A fallback) so that a message like "write an essay about the UI I built" isn't misrouted to Artifact just because "UI" appears. Rules are simple enough to unit-test exhaustively with a table of example utterances, and the pattern list is a single point of extension when a new Skill is added (§15).

If ambiguity proves to be a real problem after user testing, the router's interface (`route`) is designed to be swapped for an LLM-based classifier without changing any calling code — but that is explicitly out of scope for v1.

---

## 8. Skill Design

All Skills implement:

```
Skill:
  name: str
  run(context: SkillContext) -> SkillResult
```

where `SkillContext` carries the user message, session history, and session ID, and `SkillResult` carries `content_type` (`text` | `essay` | `artifact`), the rendered content, and optional metadata (citations, artifact code).

### Q&A Skill
- **Inputs:** user question, conversation history, retrieved transcript chunks (via `RetrievalService`).
- **Responsibilities:** construct a grounded RAG prompt, call the LLM, attach source citations (episode/guest) to the answer.
- **Outputs:** markdown-formatted answer with inline or footnote-style citations.

### Essay Skill
- **Inputs:** user's topic/prompt, optionally relevant transcript chunks for grounding (reuses `RetrievalService` when the topic maps to podcast content), style parameters (Ship30for30: short, punchy, single-idea format).
- **Responsibilities:** apply a Ship30for30-specific prompt template encoding voice/structure rules (hook, 1 idea, short paragraphs, CTA), call the LLM.
- **Outputs:** markdown-formatted short-form essay, plain text ready to publish.

### Artifact Skill
- **Inputs:** user's description of the desired UI/artifact, optional relevant context from the conversation.
- **Responsibilities:** prompt the LLM to produce self-contained HTML/CSS (and minimal vanilla JS if needed), extract the artifact block from the raw response, validate it's well-formed enough to render, attach a title/summary.
- **Outputs:** a `SkillResult` with `content_type = "artifact"`, containing the raw HTML/CSS string plus a short chat-visible description ("I've created a pricing table artifact").

Each Skill is independently testable: given a fixed context, assert on the constructed prompt and on how a canned LLM response is parsed into a `SkillResult`.

---

## 9. LLM Provider Abstraction

All three providers implement a single interface:

```
LLMProvider (interface)
  generate(messages: list[Message], **params) -> LLMResponse
```

```
                 ┌───────────────────────┐
                 │      LLMProvider       │   (interface)
                 │  generate(messages)    │
                 └───────────┬───────────┘
           ┌──────────────────┼──────────────────┐
           ▼                  ▼                  ▼
 ┌───────────────────┐ ┌───────────────────┐ ┌───────────────────┐
 │  ClaudeProvider     │ │  OpenAIProvider     │ │  OllamaProvider     │
 │  (anthropic SDK)    │ │  (openai SDK)       │ │  (local HTTP API)   │
 └───────────────────┘ └───────────────────┘ └───────────────────┘
```

A `ProviderFactory` reads `LLM_PROVIDER` (and provider-specific config: API key, model name, base URL for Ollama) from `Settings` and returns the correct concrete implementation at startup. Skills and Services depend only on the `LLMProvider` interface — they are constructed with a provider instance injected, never instantiating a provider directly. This means:

- Switching providers is a one-line environment variable change.
- Unit tests can inject a `FakeProvider` that returns canned responses, with no network calls.
- Adding a fourth provider (e.g., Gemini) means writing one new class and one factory branch — nothing else in the codebase changes.

Each concrete provider is responsible for translating the shared `Message` format into its SDK's expected shape and normalizing the response (text, token usage, stop reason) back into a shared `LLMResponse`.

---

## 10. Session Management

**New Chat**
`POST /sessions` creates a row in the `sessions` table (`id`, `title`, `created_at`, `updated_at`). Title defaults to "New chat" and is optionally auto-updated from the first user message.

**Conversation History**
Each message (`role`, `content`, `content_type`, `skill_used`, `created_at`) is persisted under its `session_id` in the `messages` table. `MessageService.get_history(session_id)` returns messages in order for both prompt construction (trimmed to a token budget) and frontend display (full history).

**Session IDs**
UUIDs generated server-side on session creation; the frontend treats them as opaque identifiers used in all subsequent `/sessions/{id}/messages` calls.

**Persistence**
PostgreSQL is the single source of truth for sessions and messages. There is no reliance on frontend-held state for anything the user expects to survive a refresh — the frontend always hydrates from `GET /sessions/{id}/messages` on load/switch.

**Loading Previous Chats**
Selecting a session in the sidebar triggers `GET /sessions/{id}/messages`; the frontend replaces its `messages[]` state with the response. Artifacts are persisted as part of the message row (content_type = "artifact", content = HTML string) so reopening a past session re-renders any artifact exactly as it was generated.

---

## 11. Artifact Rendering

**Markdown Rendering**
Standard chat responses (Q&A, essays) are rendered client-side with a markdown renderer supporting headings, lists, tables, and fenced code blocks with syntax highlighting.

**Code Rendering**
Code blocks (including the raw HTML source of an artifact, shown optionally as "view source") are rendered with a syntax highlighter, read-only, monospace.

**HTML Sandbox Rendering**
Generated HTML/CSS artifacts are rendered inside a sandboxed `<iframe>` using the `sandbox` attribute (`sandbox="allow-scripts"`, deliberately **omitting** `allow-same-origin`) and `srcDoc` rather than a `src` URL. This ensures:
- The artifact cannot access the parent page's cookies, localStorage, or DOM.
- The artifact runs in a unique, opaque origin, so even inline scripts can't reach the host application.

**Security Considerations**
- No artifact content is ever inserted directly into the host page's DOM (`dangerouslySetInnerHTML` on the main app is avoided entirely).
- The backend does not attempt to "sanitize" HTML into safety — sandboxing at render time is the actual security boundary, since sanitization of arbitrary LLM-generated HTML is unreliable.
- Artifacts are treated as **untrusted user-adjacent content** at every layer: not executed server-side, not trusted to be well-formed, and never given elevated iframe permissions.

---

## 12. Error Handling

| Failure | Strategy |
|---|---|
| **Database unavailable** | Health check endpoint reflects DB status; API returns `503` with a clear error body; frontend shows a non-blocking banner ("history unavailable, retry shortly") rather than a hard crash. |
| **Missing API key** | Detected at startup via `Settings` validation for the *configured* provider only; app fails fast with a descriptive log message rather than failing on the first user request. |
| **Ollama offline** | Provider call wrapped in a try/except that raises a typed `ProviderUnavailableError`; API layer converts this to a `503` with a message suggesting the user check the local Ollama service or switch providers. |
| **Vector database unavailable** | `RetrievalService` catches the failure and degrades gracefully: the QASkill proceeds without retrieved context (clearly flagging in the answer that it's not grounded in transcripts) rather than failing the whole chat turn. |
| **Malformed artifacts** | If the artifact parser can't find a well-formed HTML block in the LLM response, the ArtifactSkill falls back to returning the raw response as a plain-text/markdown message rather than rendering a broken iframe. |

General principle: failures in a *downstream* dependency degrade the specific feature that depends on it, they don't take down the whole request/response cycle. All caught exceptions are logged with enough context (session ID, skill, provider) to reproduce.

---

## 13. Logging Strategy

Structured JSON logging (via Python's `logging` + a JSON formatter, e.g., `structlog`) with a consistent event shape:

```json
{
  "timestamp": "...",
  "level": "INFO",
  "event": "skill.completed",
  "session_id": "...",
  "skill": "qa",
  "provider": "claude",
  "latency_ms": 842,
  "retrieved_chunks": 5
}
```

Key events logged: request received, route decision, retrieval performed (with chunk count and top score), provider call start/end (with latency), skill completion, and all handled errors (with type and downstream dependency involved). Logs never include full prompt/response bodies or secrets by default — only at `DEBUG` level, and only in local development, to avoid leaking transcript content or user data into log aggregation in a hypothetical production deployment.

---

## 14. Security Considerations

**Environment Variables**
All secrets (LLM API keys, database URL) are read exclusively from environment variables via a central Pydantic `Settings` object; nothing is hardcoded, and a `.env.example` documents required variables without real values. `.env` is git-ignored.

**Input Validation**
All API request bodies are validated through Pydantic schemas (max message length, allowed session ID format, etc.) before reaching services, rejecting malformed input at the boundary with `422`.

**HTML Sandboxing**
As described in §11, generated artifacts are isolated via iframe sandboxing with no `allow-same-origin`, so this is the primary defense against artifact-borne XSS against the host app.

**Secret Management**
No secrets are logged, returned in API responses, or sent to the frontend. Provider API keys live only in the backend process's environment. For a future production deployment, the design assumes these move into a managed secrets store (e.g., AWS Secrets Manager) without any application code change, since access is already abstracted behind `Settings`.

---

## 15. Scalability

The design supports the following extensions primarily through configuration and interface implementation, not restructuring:

**Authentication**
The API layer currently has no auth. Adding it means introducing an auth dependency (e.g., FastAPI `Depends(get_current_user)`) on routers and adding a `user_id` foreign key to `sessions` — the service and skill layers are unaffected since they already operate on `session_id`, not global state.

**Streaming**
`LLMProvider.generate` can be extended with a `generate_stream` method returning an async generator; each concrete provider already wraps an SDK that supports streaming natively. The API layer would expose this via Server-Sent Events or WebSockets without changing Skills' internal logic beyond consuming a stream instead of a single string.

**Cloud Deployment**
The backend is a stateless FastAPI process (all state in Postgres/ChromaDB), so it can be containerized and horizontally scaled behind a load balancer as-is. ChromaDB can move from local persistence to its client/server mode, and Postgres to a managed instance (RDS/Cloud SQL) — both are config changes to connection strings.

**Additional Skills**
Implement the `Skill` interface, add a routing rule to the Agent Router's pattern table, and register the skill in the Skill factory/registry. No existing Skill or router logic needs modification.

**Additional LLM Providers**
Implement the `LLMProvider` interface and register it in the `ProviderFactory`. No Skill, Service, or API code changes.

---

## 16. Design Decisions

| # | Decision | Alternative Considered | Reason Chosen |
|---|---|---|---|
| 1 | Rule-based keyword router for skill selection | LLM-based intent classification | Deterministic, zero extra latency/cost, easy to test exhaustively; sufficient accuracy for three well-differentiated skills |
| 2 | ChromaDB for vector storage | Pinecone / Weaviate / pgvector | Embedded, zero external infra, fast local iteration; sufficient scale for a single podcast's transcripts |
| 3 | PostgreSQL for session persistence | SQLite / MongoDB | Production-realistic relational store with strong consistency for structured session/message data; easy managed-cloud migration path |
| 4 | Shared `LLMProvider` interface with a factory | Direct SDK calls per skill | Decouples business logic from any single vendor; enables configurable provider swap and easy testing with fakes |
| 5 | Layered backend (API → Services → Skills → Providers → DB) | Fat routers with inline logic | Keeps each concern independently testable and readable; mirrors standard separation-of-concerns practice |
| 6 | iframe sandboxing (no server-side HTML sanitization) for artifacts | Server-side HTML sanitizer library | Sanitizing arbitrary LLM-generated HTML reliably is hard; sandboxing provides an actual, verifiable security boundary |
| 7 | Chunking on speaker/paragraph boundaries with overlap | Fixed-size character chunking | Preserves semantic coherence of transcript chunks, improving retrieval relevance and citation quality |
| 8 | Prompt templates as versioned files, not inline strings | Inline f-strings in skill code | Enables prompt iteration/review separate from code changes; keeps Skills focused on orchestration, not prompt copy |
| 9 | Config via environment variables + central `Settings` object | Scattered `os.getenv` calls | Single source of truth for configuration, validated at startup, easy to document via `.env.example` |
| 10 | Graceful degradation when ChromaDB is unavailable | Hard failure of the whole chat turn | Keeps the assistant usable (as a general chat) even if the retrieval subsystem is down, improving perceived reliability |
| 11 | React Query/SWR for server-state caching on the frontend | Hand-rolled fetch + local state | Reduces boilerplate cache-invalidation bugs around sessions/messages; well-understood, widely adopted pattern |
| 12 | Skill interface returns structured `SkillResult`, not raw text | Skills return raw strings | Lets the API/frontend handle text, essay, and artifact content types uniformly and safely, without string-sniffing |

---

## 17. Trade-offs

- **Rule-based routing over LLM classification** trades a small amount of routing flexibility (edge-case phrasing might be misrouted) for zero added latency, zero added cost, and full determinism/testability. The router's interface is intentionally isolated so this trade-off can be revisited later without touching Skills.

- **No authentication in v1** trades away multi-tenant security for a much simpler API surface appropriate to the assignment's scope. This is acceptable because the design already anticipates auth as a thin addition (§15) rather than a rewrite.

- **No streaming in v1** trades a more polished perceived-latency UX for simpler request/response handling on both frontend and backend. The provider interface is shaped so streaming can be added later as an additive method, not a redesign.

- **Local/embedded ChromaDB instead of a managed vector service** trades production-grade horizontal scalability of the vector store for zero infrastructure setup cost — appropriate for a single podcast's transcript corpus, but a deliberate ceiling that would need revisiting (client/server ChromaDB, or a managed alternative) at meaningfully larger corpus size or query volume.

- **No server-side HTML sanitization for artifacts** trades a "belt and suspenders" defense-in-depth posture for relying on a single, well-understood security boundary (iframe sandboxing). This is a deliberate simplification: an unreliable sanitizer that gives false confidence is arguably worse than no sanitizer plus a real sandbox.

- **Prompt templates as flat files rather than a prompt-management service** trades sophisticated versioning/experimentation tooling (e.g., A/B testing prompts, prompt registries) for simplicity appropriate to the current scale — acceptable now, with the file-based approach cleanly upgradeable to a dedicated prompt store later since Skills already treat "get the prompt" as an abstracted step.

- **Single default embedding-model-per-provider-family** trades embedding quality optimization (mixing/matching embedding models regardless of chat provider) for simpler configuration and fewer moving parts; the embedding step is still isolated behind its own function, so this can be decoupled later without touching retrieval logic.

Overall, every trade-off made favors **shipping a clean, correctly-layered v1** over speculatively building for scale the assignment doesn't require — while ensuring none of these choices are structurally difficult to reverse.
