# Development Plan

## 1. Document Header

| Field | Value |
|---|---|
| **Project** | The Lenny Growth Assistant |
| **Document** | Development Plan (`docs/development_plan.md`) |
| **Purpose** | To define how the system described in the PRD, System Architecture, Database Design, and API Design documents will actually be built — the engineering standards, repository layout, workflow, milestones, and operational practices that translate approved design into working software. |
| **Audience** | Backend engineers, frontend engineers, DevOps/infrastructure engineers, QA engineers, technical leads, and academic/industry reviewers assessing engineering rigor. |
| **Dependencies** | `docs/prd.md`, `docs/system_architecture.md`, `docs/database_design.md`, `docs/api_design.md` |
| **Status** | Approved for Implementation |
| **Version** | 1.0.0 |

This document intentionally does not restate product requirements, architectural diagrams, schema definitions, or endpoint contracts — those live in their respective source documents and are treated as binding inputs here. What follows is the operational bridge between "what we agreed to build" and "how engineers will build it, in what order, under what standards, and with what safeguards."

---

## 2. Development Philosophy

Every technical decision in this plan traces back to a small set of guiding principles. They are stated explicitly here so that when an engineer faces an ambiguous implementation choice later, they have a consistent frame of reference rather than having to guess at intent.

### 2.1 Incremental Development

The system is built in vertical, demonstrable slices rather than horizontal layers that only integrate at the end. Each milestone (Section 9) produces something that can be run, inspected, and tested — a working database layer before the API that depends on it, a working API before the RAG pipeline that calls it, a working RAG pipeline before the frontend that displays its output. This is chosen because the project combines several genuinely hard subsystems (LLM orchestration, retrieval-augmented generation, multi-provider AI integration) where late integration risk is the single greatest threat to a project of this shape. Surfacing integration problems early, while the surrounding code is still small and well understood, is far cheaper than discovering them after the frontend has been built against a set of assumptions the backend cannot support.

### 2.2 Modular Architecture

The backend is decomposed into independent, single-responsibility modules (API layer, service layer, repository layer, agents, RAG, LLM abstraction) that communicate through well-defined interfaces rather than through shared, mutable global state. This matters specifically for this project because it uses three interchangeable AI providers (Anthropic, OpenAI, Ollama). If provider-specific logic were scattered across the codebase, adding, removing, or swapping a provider would require touching dozens of files. With a modular `llm/` package that presents one abstraction to the rest of the system, provider changes are contained to a single boundary.

### 2.3 Clean Code Principles

Code is written to be read by the next engineer, not just executed by the interpreter. This means descriptive naming over comments that explain unclear code, small functions with a single purpose, and avoidance of deep nesting and implicit side effects. This is a deliberate cost/benefit trade: clean code takes marginally longer to write and pays that cost back every single time someone (including the original author, months later) has to modify it.

### 2.4 SOLID Principles

- **Single Responsibility** — each class or module has one reason to change (a repository changes only if the persistence mechanism changes; a service changes only if business logic changes).
- **Open/Closed** — the LLM abstraction is open for extension (new providers can be added) but closed for modification (existing provider implementations and calling code do not need to change).
- **Liskov Substitution** — any concrete LLM provider client can be substituted for another behind the shared interface without breaking callers.
- **Interface Segregation** — services depend on narrow, purpose-built interfaces (e.g., a `VectorStoreReader` interface) rather than large, do-everything classes.
- **Dependency Inversion** — high-level modules (services) depend on abstractions (repository interfaces, LLM interfaces), not on concrete low-level implementations, which are injected at runtime.

These are followed because the project's core risk is coupling to volatile external systems — three different AI providers, a vector database, and a relational database. SOLID principles, applied specifically at those boundaries, are what make the system resilient to those components changing independently.

### 2.5 Separation of Concerns

Presentation (React), orchestration (FastAPI routes and services), domain logic (agents, RAG pipeline), and persistence (SQLAlchemy repositories, ChromaDB) are kept in distinct layers that do not reach across boundaries. A route handler never issues a raw SQL query, and a repository never contains business rules. This is what allows the backend and frontend teams to work in parallel without stepping on each other, and what allows the RAG pipeline to be unit-tested without needing a live database.

### 2.6 Dependency Injection

FastAPI's native dependency injection system (`Depends`) is used throughout to supply services, repositories, database sessions, and configuration to route handlers, rather than importing and instantiating them inline. This is chosen because it is the single change that makes the codebase testable: in a test, a real PostgreSQL-backed repository can be swapped for an in-memory fake, and a real Anthropic client can be swapped for a mock, without modifying the code under test.

### 2.7 Maintainability

Maintainability is treated as a first-class requirement, not an afterthought. Consistent formatting (Black, Ruff, isort — Section 4), consistent structure (Section 3), and consistent documentation (docstrings, this plan, agent transcripts — Section 13) all exist to reduce the cognitive overhead required for a new contributor to become productive.

### 2.8 Scalability

While the initial deployment target is a single-host Docker Compose stack (Section 8), the architecture avoids decisions that would make horizontal scaling difficult later: statelessness in the API layer, externalized session/config state, and a repository pattern that would allow PostgreSQL connection pooling or read replicas to be introduced without touching business logic. Scalability is designed for without being prematurely implemented — the plan does not build infrastructure the current requirements do not need, but it also does not paint the project into a corner.

---

## 3. Repository Structure

The repository root separates the two applications (backend, frontend), the AI/data assets (chroma, transcripts), operational tooling (scripts), and process artifacts (docs, agent_transcripts) so that any engineer can locate the right place for new code within seconds of opening the project.

```
project-root/
│
├── backend/                  # FastAPI application (all server-side code)
├── frontend/                 # React + TypeScript application
├── chroma/                   # Persisted ChromaDB vector store data (volume-mounted)
├── transcripts/              # Source conversation/growth transcripts ingested by the system
├── scripts/                  # One-off and recurring operational scripts (seeding, migrations helpers, ingestion)
├── docs/                     # Living project documentation (PRD, architecture, this plan, etc.)
├── agent_transcripts/        # Preserved AI coding agent session logs (Section 13)
├── docker-compose.yml        # Multi-container orchestration definition
├── docker-compose.override.yml   # Local development overrides (hot reload, bind mounts)
├── .env.example               # Template for required environment variables
├── .gitignore
└── README.md                  # Project overview, setup instructions, quick start
```

### 3.1 Backend Structure

```
backend/
│
├── app/
│   ├── api/                  # FastAPI routers — HTTP boundary only
│   │   ├── v1/
│   │   │   ├── endpoints/    # One file per resource (chat.py, users.py, transcripts.py, artifacts.py)
│   │   │   └── router.py     # Aggregates all v1 routers into one APIRouter
│   │   └── deps.py           # Shared FastAPI dependencies (get_db, get_current_user, get_llm_client)
│   │
│   ├── models/                # SQLAlchemy ORM models — one file per domain entity
│   ├── schemas/                # Pydantic V2 models — request/response contracts, kept separate from ORM models
│   ├── services/               # Business logic layer — orchestrates repositories, agents, and LLM calls
│   ├── repositories/           # Data access layer — the only code allowed to issue queries
│   ├── agents/                 # Agentic workflows built on top of services (e.g., growth-plan agent)
│   ├── rag/                    # Retrieval-augmented generation pipeline (chunking, embedding, retrieval)
│   ├── llm/                    # Provider abstraction layer (Anthropic, OpenAI, Ollama behind one interface)
│   ├── middleware/             # Cross-cutting HTTP concerns (request logging, error handling, CORS)
│   ├── database/               # Engine/session setup, Alembic environment, base declarative class
│   ├── core/                   # Application-wide concerns: config loading, security, exceptions, constants
│   ├── utils/                  # Small, stateless helper functions with no business meaning of their own
│   ├── config/                 # Environment-specific settings objects (Pydantic Settings)
│   └── main.py                 # Application factory / ASGI entrypoint
│
├── alembic/
│   ├── versions/                # Auto-generated and hand-reviewed migration scripts
│   └── env.py
│
├── tests/
│   ├── unit/
│   ├── integration/
│   └── conftest.py
│
├── pyproject.toml               # Dependency + tool configuration (Black, Ruff, isort, pytest)
├── alembic.ini
└── Dockerfile
```

**Why each backend directory exists:**

| Directory | Responsibility | What Belongs There |
|---|---|---|
| `api/` | Translate HTTP requests into service calls and service results back into HTTP responses. | Route decorators, request parsing, status codes, response models. No business logic, no direct database access. |
| `models/` | Define the persistent shape of data as SQLAlchemy declarative classes. | Table definitions, relationships, column constraints. Mirrors `docs/database_design.md`. |
| `schemas/` | Define the external contract of the API, independent of how data is stored. | Pydantic V2 request/response models, validators. Kept separate from `models/` so the database schema can evolve without breaking the API contract, and vice versa. |
| `services/` | Encapsulate business rules and orchestrate multi-step operations. | E.g., "generate a growth plan" coordinates the RAG pipeline, an LLM call, and a repository write — that coordination logic lives here, not in a route or a repository. |
| `repositories/` | Isolate all persistence logic behind a stable interface. | CRUD operations, query construction. Services never see SQLAlchemy `Session` objects directly. |
| `agents/` | Implement higher-level, multi-step AI-driven workflows. | Anything that chains multiple LLM calls, tool calls, or RAG lookups into one coherent task (e.g., a "growth assistant" agent that plans, retrieves, and drafts). |
| `rag/` | Own the retrieval-augmented generation pipeline end to end. | Document chunking, embedding generation, ChromaDB read/write, context assembly for prompts. |
| `llm/` | Abstract away differences between Anthropic, OpenAI, and Ollama. | A common `LLMClient` interface plus one concrete adapter per provider, selected via configuration. |
| `middleware/` | Apply behavior to every request without every route needing to opt in. | Request ID injection, structured logging, global exception handling, CORS. |
| `database/` | Own the mechanics of talking to PostgreSQL. | Engine/session factory, declarative base, Alembic wiring. |
| `core/` | Hold concerns that the whole application depends on. | Settings loading, custom exception classes, security utilities (hashing, token handling). |
| `utils/` | Provide small, reusable, side-effect-free helpers. | Date formatting, text truncation, slugification — nothing that touches the database or an external API. |
| `config/` | Centralize environment-aware configuration. | Pydantic `BaseSettings` classes that read from environment variables (Section 7). |

### 3.2 Frontend Structure

```
frontend/
│
├── src/
│   ├── components/            # Reusable, presentation-focused UI components
│   ├── pages/                 # Route-level components composed from smaller components
│   ├── hooks/                 # Custom React hooks encapsulating reusable stateful logic
│   ├── api/                   # Axios client instances and typed API call functions
│   ├── types/                 # Shared TypeScript interfaces/types, mirroring backend schemas
│   ├── context/                # React Context providers for cross-cutting UI state
│   ├── utils/                  # Stateless helper functions
│   ├── styles/                 # Tailwind configuration and any global CSS
│   ├── App.tsx
│   └── main.tsx
│
├── public/
├── index.html
├── tailwind.config.ts
├── vite.config.ts
├── tsconfig.json
├── package.json
└── Dockerfile
```

### 3.3 Supporting Directories

```
chroma/                 # Bind-mounted volume for ChromaDB's persistent index — not committed except a .gitkeep
transcripts/            # Raw source material the RAG pipeline ingests (growth conversation transcripts)
scripts/
├── seed_db.py          # Populates a fresh database with baseline reference data
├── ingest_transcripts.py   # Batch-loads transcripts/ into the RAG pipeline
└── wait_for_db.sh       # Used by Docker healthchecks/entrypoints
agent_transcripts/       # See Section 13
docs/                     # See Section 1 dependencies
```

---

## 4. Backend Development Standards

| Standard | Choice | Why |
|---|---|---|
| **Python Version** | 3.12 | Latest stable release at project start; brings performance improvements and modern typing syntax (`X \| Y` unions, improved generics) that keep type hints concise. |
| **Web Framework** | FastAPI | Native async support, automatic OpenAPI generation directly from Pydantic schemas, and first-class dependency injection — all of which this project relies on heavily. |
| **ORM** | SQLAlchemy (2.0-style) | Mature, explicit, and works well with Alembic; the 2.0 query style aligns with the repository pattern used here. |
| **Migrations** | Alembic | Keeps schema changes versioned, reviewable, and reversible — essential once the database design in `docs/database_design.md` starts evolving during implementation. |
| **Validation** | Pydantic V2 | Faster (Rust core) than V1, and used both for API schemas and for typed application settings, giving one validation mental model across the whole backend. |
| **Type Hints** | Mandatory on all function signatures | Type hints are treated as executable documentation; combined with Ruff/mypy-style checks they catch a large class of bugs before runtime and make IDE assistance far more useful. |
| **Formatter** | Black | Removes formatting as a topic of discussion or code review friction — one canonical style, enforced automatically. |
| **Linter** | Ruff | Extremely fast, replaces multiple older tools (Flake8, isort's linting rules, pyupgrade) with one configurable binary, keeping CI fast. |
| **Import Sorting** | isort (or Ruff's isort-compatible rule set) | Consistent import ordering makes diffs smaller and merge conflicts rarer. |
| **Logging** | Python `logging` with structured (JSON-capable) formatters | Plain print statements are unsuitable for a multi-container system; structured logs are what make Section 11's monitoring approach viable. |
| **Dependency Injection** | FastAPI `Depends` | See Section 2.6 — the mechanism that makes services and repositories testable and swappable. |
| **Repository Pattern** | Enforced — no ORM/session objects outside `repositories/` | Prevents query logic from leaking into services or routes, and gives a single place to optimize or change persistence behavior. |
| **Service Layer Pattern** | Enforced — all business logic in `services/` | Keeps route handlers thin and keeps business rules testable independent of HTTP. |
| **Error Handling** | Custom exception hierarchy (`core/exceptions.py`) + global FastAPI exception handlers | Ensures every error returned to a client has a consistent shape, and that internal exceptions never leak stack traces to the frontend. |
| **Configuration Management** | Pydantic `BaseSettings`, reading from `.env`/environment variables | Centralizes all configuration in a typed, validated object rather than scattered `os.environ.get()` calls, catching misconfiguration at startup instead of at first use. |
| **Naming Conventions** | `snake_case` for modules/functions/variables, `PascalCase` for classes, `UPPER_SNAKE_CASE` for constants | Standard, unambiguous PEP 8 convention that every Python engineer already knows. |
| **File Organization** | One class/concept per file where reasonable; files grouped by layer, not by feature alone | Balances discoverability (you know `services/` holds business logic) with navigability (files stay small). |
| **Async Programming** | `async def` for all I/O-bound route handlers, service methods, and repository calls that touch the database or an external LLM API | FastAPI's performance advantage is realized only when I/O-bound code is actually async; this matters especially for LLM calls, which can take several seconds and would otherwise block a worker. |

---

## 5. Frontend Development Standards

| Standard | Choice | Why |
|---|---|---|
| **Framework** | React | Component model matches the UI's composition of chat views, transcript panels, and artifact displays; large ecosystem and hiring pool. |
| **Language** | TypeScript | Shares typed contracts with the backend's Pydantic schemas (via hand-maintained or generated types in `src/types/`), catching integration mismatches at compile time rather than at runtime. |
| **Build Tool** | Vite | Near-instant dev server startup and hot module replacement, which matters for iteration speed across the many small components this UI needs. |
| **Styling** | TailwindCSS | Utility-first styling keeps styling co-located with markup, avoids a separate CSS architecture to maintain, and enforces a consistent design scale (spacing, color) across the app. |
| **HTTP Client** | Axios | Interceptor support is used to attach auth headers and to centralize error handling for API failures, in one place rather than duplicated across every fetch call. |
| **Routing** | React Router | Standard, well-supported routing library that fits the page-based structure in `src/pages/`. |
| **State Management** | React built-in state (`useState`, `useReducer`) plus Context for cross-cutting concerns; no external state library initially | The application's shared state (current session, active provider, user preferences) is small enough that Redux/Zustand would add ceremony without a corresponding benefit; this can be revisited if state complexity grows (Section 16). |
| **Hooks** | Custom hooks for reusable stateful logic (e.g., `useChatSession`, `useArtifacts`) | Keeps components focused on rendering and extracts logic that would otherwise be duplicated across pages. |
| **Component Design** | Small, composable, presentation-focused components in `components/`; orchestration lives in `pages/` | Mirrors the backend's separation of concerns — presentation components don't know about Axios, and API-calling logic doesn't know about JSX. |
| **Folder Structure** | Feature-agnostic layering (`components/`, `pages/`, `hooks/`, `api/`) as described in Section 3.2 | Chosen over a feature-folder structure because the application's features overlap heavily (chat, transcripts, and artifacts all share components), and a layered structure keeps shared pieces from being duplicated. |
| **Naming Convention** | `PascalCase` for components and their files, `camelCase` for functions/variables/hooks, `useX` prefix for hooks | Matches React community convention, making the codebase immediately familiar to any React engineer. |
| **API Layer** | Typed functions in `src/api/`, one module per backend resource, wrapping Axios calls | No component calls Axios directly; this is the frontend's equivalent of the backend's repository pattern, and makes it possible to change the HTTP client or base URL in one place. |
| **Error Handling** | Axios response interceptor for global errors (auth, network) + local try/catch for per-request UI feedback | Ensures a network failure or 500 response always produces a user-visible state rather than a silently broken UI. |

---

## 6. Git Workflow

A trunk-based-with-features model is used, balancing the stability of `main` against the need for parallel work across distinct subsystems.

```
main
 └── development
      ├── feature/database
      ├── feature/chat
      ├── feature/rag
      ├── feature/frontend
      └── feature/testing
```

**Branching flow:** `main` always reflects the last known-good, deployable state of the project. `development` is the integration branch where completed feature branches land first. Each `feature/*` branch is scoped to one milestone-sized unit of work (Section 9) and is created from the latest `development`. This structure is chosen because it isolates risk: a half-finished RAG pipeline on `feature/rag` cannot destabilize the frontend team working on `feature/frontend` from the same `development` baseline.

**Pull requests:** Every feature branch is merged into `development` via a pull request, never a direct push. A pull request must include a description of what changed and why, a link to the relevant milestone, and confirmation that the relevant test suite passes locally. This creates a written record of intent alongside the code, and gives at least one other contributor (or, in a solo-engineering context, a deliberate self-review pass) a chance to catch issues before they compound.

**Merge strategy:** Squash-and-merge is used for feature branches into `development`, producing one clean commit per feature that summarizes the whole unit of work; `development` is merged into `main` with a regular merge commit at the close of each milestone, preserving the milestone boundary in history. This keeps `main`'s history readable at a glance while still preserving the more granular history of `development` for anyone who needs to dig deeper.

**Commit message convention:** Conventional Commits is used — `type(scope): summary`, for example `feat(rag): add chunking pipeline for transcripts` or `fix(api): correct pagination offset in chat history`. Common types are `feat`, `fix`, `refactor`, `test`, `docs`, and `chore`. This convention is chosen because it is machine-parseable (enabling future changelog automation) and forces the author to state, in a few words, exactly what changed and where — a useful discipline in itself.

---

## 7. Environment Variables

All configuration that varies between environments (local development, CI, production) or that is sensitive is supplied via environment variables, never hard-coded. A `.env.example` file documents every variable without exposing real values.

| Variable | Purpose |
|---|---|
| `POSTGRES_HOST` | Hostname of the PostgreSQL server the backend connects to (the Docker Compose service name in containerized environments). |
| `POSTGRES_PORT` | Port PostgreSQL listens on (default `5432`), kept configurable in case of port conflicts or non-default deployments. |
| `POSTGRES_DB` | Name of the database the application uses, allowing separate databases per environment (dev, test, prod) on the same server. |
| `POSTGRES_USER` | Username the backend authenticates to PostgreSQL with. |
| `POSTGRES_PASSWORD` | Password for the above user; always injected via environment/secret store, never committed. |
| `DATABASE_URL` | Fully assembled SQLAlchemy connection string, either composed from the above variables or provided directly (e.g., in managed-database deployments where the components above don't apply cleanly). |
| `OPENAI_API_KEY` | Authenticates backend requests to the OpenAI API when OpenAI is the selected or fallback LLM provider. |
| `ANTHROPIC_API_KEY` | Authenticates backend requests to the Anthropic API when Claude is the selected provider. |
| `OLLAMA_BASE_URL` | Base URL of the locally/self-hosted Ollama instance, used when a local model is the selected provider — keeps local inference configurable independent of code changes. |
| `CHROMA_HOST` | Hostname of the ChromaDB service the RAG pipeline connects to. |
| `CHROMA_PORT` | Port ChromaDB listens on. |
| `LOG_LEVEL` | Controls verbosity of application logging (`DEBUG`, `INFO`, `WARNING`, `ERROR`) — set higher in production to reduce noise, lower during active debugging. |
| `SECRET_KEY` | Used for signing/security-sensitive operations (e.g., token signing if authentication is added per Section 16); always environment-supplied and rotated per deployment. |

Every variable is validated at application startup through the Pydantic `Settings` object in `app/config/`, so a missing or malformed value fails fast with a clear error rather than surfacing as a confusing runtime failure deep in a request.

---

## 8. Docker Strategy

The system is fully containerized so that "it works on my machine" is never a meaningful distinction from "it works" — every engineer, and eventual deployment target, runs the identical set of services.

| Container | Base Purpose | Notes |
|---|---|---|
| **frontend** | Serves the built React application (development: Vite dev server with HMR; production: static build behind a lightweight server). | Rebuilt whenever `frontend/` dependencies or source change. |
| **backend** | Runs the FastAPI application via Uvicorn. | Mounts `backend/app` as a bind volume in development for live reload; runs from a built image in production. |
| **postgres** | Official PostgreSQL image, holds all relational data described in `docs/database_design.md`. | Data persisted via a named volume so container recreation does not lose data. |
| **chromadb** | Official ChromaDB image, holds the vector index used by the RAG pipeline. | Data persisted via a bind mount to `chroma/` so the index survives container rebuilds and is inspectable on the host. |
| **ollama** *(optional)* | Runs local open-source models when the LLM provider is configured to use Ollama instead of a hosted API. | Only started when the `ollama` Compose profile is enabled, since it is not required for every developer's workflow and has a much larger resource footprint. |

**Networks:** All containers share a single user-defined Docker Compose network, allowing services to address each other by service name (e.g., the backend reaches PostgreSQL at `postgres:5432`) rather than by fragile hard-coded IPs, and keeping the stack isolated from other Docker workloads on the same host.

**Volumes:** Named volumes are used for PostgreSQL's data directory (survives `docker compose down`, only cleared by an explicit `-v`), and a bind mount is used for ChromaDB so its index is directly visible and backupable from the host filesystem at `chroma/`.

**Restart policies:** All long-running services use `restart: unless-stopped`, so a container that crashes (or a host that reboots) recovers automatically without manual intervention, while still respecting an intentional `docker compose stop`.

**Health checks:** PostgreSQL and ChromaDB each define a Compose healthcheck (e.g., `pg_isready` for Postgres); the backend's `depends_on` clauses use `condition: service_healthy` rather than a plain startup-order dependency, so the API does not begin accepting traffic — or fail its own startup — before its dependencies are actually ready to serve requests.

**Container communication:** All inter-service communication happens over the internal Docker network using service names as hostnames, configured through the environment variables in Section 7 rather than hard-coded addresses — this is what allows the exact same backend image to run correctly in both local Compose and a future non-Compose deployment target, by changing only environment values.

**Development vs. production:** `docker-compose.yml` defines the production-shaped baseline (built images, no source bind mounts); `docker-compose.override.yml` — automatically applied by Compose in local development — adds source-code bind mounts and reload flags. This split keeps a single source of truth for service topology while still giving developers fast local iteration.

---

## 9. Development Milestones

Each milestone is scoped so its completion criteria can be verified independently, in line with the incremental philosophy in Section 2.1.

### Milestone 1 — Project Setup
- **Objectives:** Establish the repository skeleton (Section 3), Docker Compose stack, base FastAPI and React applications, and tooling configuration (Black, Ruff, isort, ESLint/Prettier equivalents).
- **Deliverables:** A running `docker compose up` that serves an empty FastAPI health endpoint and an empty React landing page.
- **Dependencies:** None — this is the foundation milestone.
- **Completion Criteria:** All containers start healthy; `GET /health` returns `200`; frontend loads in a browser and successfully calls the health endpoint.

### Milestone 2 — Database Layer
- **Objectives:** Implement all SQLAlchemy models from `docs/database_design.md`, configure Alembic, and produce the initial migration.
- **Deliverables:** `app/models/`, `app/database/`, initial Alembic migration, seed script.
- **Dependencies:** Milestone 1.
- **Completion Criteria:** `alembic upgrade head` runs cleanly against a fresh database; seed script populates baseline data without error.

### Milestone 3 — REST API
- **Objectives:** Implement the endpoints defined in `docs/api_design.md`, wired through the service and repository layers.
- **Deliverables:** `app/api/`, `app/schemas/`, `app/services/`, `app/repositories/`, corresponding unit tests.
- **Dependencies:** Milestone 2.
- **Completion Criteria:** All endpoints in the API design are implemented, return schema-valid responses, and are covered by at least one passing test each.

### Milestone 4 — LLM Integration
- **Objectives:** Build the provider-agnostic `llm/` abstraction and concrete adapters for Anthropic, OpenAI, and Ollama.
- **Deliverables:** `app/llm/`, provider selection via configuration, mocked-provider test suite.
- **Dependencies:** Milestone 3.
- **Completion Criteria:** A single service call can complete successfully against each of the three providers (verified individually), with provider selection controlled purely by configuration.

### Milestone 5 — RAG Pipeline
- **Objectives:** Implement transcript chunking, embedding, ChromaDB storage, and retrieval-augmented prompt assembly.
- **Deliverables:** `app/rag/`, `scripts/ingest_transcripts.py`, integration tests against a live ChromaDB instance.
- **Dependencies:** Milestones 2 and 4.
- **Completion Criteria:** Ingesting the sample `transcripts/` corpus produces retrievable, relevant chunks for a representative set of test queries.

### Milestone 6 — Artifact Generation
- **Objectives:** Implement the agent workflow(s) in `app/agents/` that combine RAG retrieval and LLM calls into finished growth-assistant artifacts (e.g., growth plans, summaries).
- **Deliverables:** `app/agents/`, associated API endpoints, persistence of generated artifacts.
- **Dependencies:** Milestones 4 and 5.
- **Completion Criteria:** An end-to-end request produces a persisted, retrievable artifact grounded in retrieved transcript content.

### Milestone 7 — Frontend
- **Objectives:** Build the full React UI — chat interface, transcript browsing, artifact display — against the now-complete API.
- **Deliverables:** `frontend/src/` fully implemented per Section 5.
- **Dependencies:** Milestone 6 (functionally complete API).
- **Completion Criteria:** A user can complete the full primary workflow (initiate a session, retrieve grounded responses, view a generated artifact) entirely through the UI.

### Milestone 8 — Testing
- **Objectives:** Fill coverage gaps, add end-to-end tests, and formalize the test suite described in Section 10.
- **Deliverables:** Completed `backend/tests/`, frontend test suite, coverage report.
- **Dependencies:** Milestone 7.
- **Completion Criteria:** Coverage thresholds defined in Section 10 are met; CI runs the full suite successfully.

### Milestone 9 — Deployment
- **Objectives:** Finalize production Docker images, verify the full Compose stack under production-like configuration, and document operational runbooks.
- **Deliverables:** Production `docker-compose.yml` validated end-to-end, deployment notes in `README.md`.
- **Dependencies:** Milestone 8.
- **Completion Criteria:** A clean `git clone` followed by `docker compose up` on a fresh host produces a fully functional system using only documented configuration steps.

---

## 10. Testing Strategy

| Layer | Approach | Rationale |
|---|---|---|
| **Framework** | pytest (backend), Vitest/React Testing Library (frontend) | pytest's fixture system pairs naturally with FastAPI's dependency injection, letting tests override dependencies cleanly; RTL encourages testing components the way a user interacts with them rather than their internals. |
| **Unit Tests** | Cover services, repositories (against a test database), RAG chunking logic, and LLM adapters (mocked) in isolation. | Fast feedback and precise failure localization — a broken chunking function should fail one unit test, not a slow end-to-end run. |
| **Integration Tests** | Exercise real interactions between the API, database, and ChromaDB using containerized test dependencies. | Catches issues unit tests structurally cannot — real SQL behavior, real vector similarity results. |
| **API Tests** | FastAPI's `TestClient` drives full request/response cycles against the running application. | Verifies the actual contract in `docs/api_design.md` is honored, not just the underlying logic. |
| **Mocking LLM Providers** | All three provider adapters are mockable via the shared `LLMClient` interface (Section 4); unit and CI tests never make real, billed API calls. | Keeps tests fast, deterministic, and free of external cost or flakiness from provider downtime. |
| **Database Testing** | A dedicated test database, created and migrated fresh per test session, with transactional rollback between tests. | Guarantees test isolation — no test's data can leak into another's. |
| **Frontend Testing** | Component tests for presentational components, hook tests for `hooks/`, and a small number of end-to-end tests for the primary user flow. | Matches effort to risk — most bugs live in logic-bearing hooks and API integration, not in static markup. |
| **Coverage** | Minimum 80% line coverage on `services/`, `repositories/`, `rag/`, and `llm/`; coverage tracked but not gated to 100% everywhere. | These modules carry the system's actual risk; chasing 100% coverage on trivial glue code wastes effort without reducing real risk. |
| **Test Organization** | Mirrors `app/` structure inside `tests/unit/` and `tests/integration/`, one test file per source file as a default. | An engineer can always find a module's tests by mirroring its path, with no separate mental index required. |
| **Continuous Testing** | Full suite runs on every pull request into `development`; a pre-commit hook runs formatting/lint checks locally. | Keeps `development` continuously verified rather than accumulating untested changes that surface as one large integration failure. |

---

## 11. Logging and Monitoring

| Aspect | Approach | Rationale |
|---|---|---|
| **Logging Levels** | Standard `DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`, controlled via the `LOG_LEVEL` environment variable. | Lets the same code run verbosely in development and quietly in production without code changes. |
| **Structured Logs** | Logs are emitted as structured (JSON-capable) records rather than free-form strings. | Structured logs can be filtered, aggregated, and fed into log-processing tools later (Section 16) without a rewrite. |
| **Request IDs** | A unique request ID is generated per incoming HTTP request in middleware and attached to every log line produced while handling it. | Makes it possible to trace one user's request across the API, service, and RAG layers even when logs from concurrent requests interleave. |
| **Error Logging** | All unhandled exceptions are caught by a global FastAPI exception handler, logged with full context and the request ID, and translated into a safe, generic client-facing error. | Ensures no error is silently lost, while never exposing internal stack traces or details to the frontend. |
| **Performance Logging** | Key operations (LLM calls, RAG retrieval, database queries above a threshold) log their duration. | LLM and vector-search latency are the two most likely sources of user-facing slowness in this system, so they are instrumented from day one rather than added reactively after a complaint. |
| **Log Rotation** | Container logs are size- and time-bound via Docker's logging driver configuration. | Prevents unbounded log growth from filling host disk during long-running deployments. |
| **Future Monitoring** | The structured logging and request-ID foundation is designed to feed a future observability stack (Section 16) without rework. | Avoids building a throwaway logging approach that would need to be replaced rather than extended. |

---

## 12. Security Considerations

| Concern | Approach |
|---|---|
| **Environment Variables** | All secrets (API keys, database credentials, `SECRET_KEY`) are supplied exclusively through environment variables, never committed to source control; `.env` is git-ignored and only `.env.example` (with placeholder values) is tracked. |
| **Input Validation** | Every API input is validated at the boundary through Pydantic V2 schemas before it reaches any service or repository code, rejecting malformed requests before they can cause downstream errors. |
| **SQL Injection Protection** | All database access goes through SQLAlchemy's parameterized query construction inside `repositories/`; no raw string-interpolated SQL is permitted anywhere in the codebase. |
| **XSS Protection** | React escapes rendered content by default; any place the UI must render externally sourced or LLM-generated content as HTML is explicitly reviewed and sanitized rather than rendered via `dangerouslySetInnerHTML` without inspection. |
| **HTML Sanitization** | LLM-generated content that may include markup is passed through a sanitization step before rendering, since generated text is treated as untrusted input, not as trusted application output. |
| **Secrets Management** | API keys for Anthropic and OpenAI, and the PostgreSQL password, are treated as the highest-sensitivity configuration values, injected at container runtime and never logged, even at `DEBUG` level. |
| **Docker Security** | Containers run with least-privilege where practical (non-root application user in custom images), and only the ports actually required (frontend, backend) are published to the host — the database and vector store are reachable only on the internal Compose network. |
| **Future Authentication** | The current milestone set does not include user authentication (single-tenant/local use is the initial target), but the service-layer boundary and dependency-injection structure are designed so that an authentication dependency (e.g., `get_current_user`) can be added to `app/api/deps.py` and applied to routes without restructuring the codebase — see Section 16. |

---

## 13. Coding Agent Workflow

This project is built with the assistance of AI coding agents, and the process by which that assistance is used, reviewed, and recorded is treated as part of the engineering discipline of the project, not as an implementation detail to be hidden.

**Workflow stages:**

1. **Requirement Analysis** — before any prompt is written, the relevant section of the PRD, architecture, database design, API design, or this development plan is identified as the source of truth for the task at hand.
2. **Prompt Preparation** — a specific, scoped prompt is composed, referencing the exact requirement and any relevant existing code, rather than a vague open-ended request.
3. **Code Generation** — the coding agent produces an implementation attempt.
4. **Manual Review** — every generated change is read line by line by an engineer before being accepted; nothing generated is merged unread.
5. **Testing** — the relevant test suite (Section 10) is run against the generated code.
6. **Bug Fixing** — failures are diagnosed and corrected, either by refining the prompt and regenerating, or by direct manual edit, whichever is faster and clearer for the specific defect.
7. **Validation** — the fixed implementation is re-tested and checked against the originating requirement to confirm it actually satisfies it, not merely that it runs.
8. **Iteration** — steps 2–7 repeat as needed until the requirement is fully and correctly satisfied.
9. **Documentation** — the finished, working exchange (and any notable failed attempts along the way) is written up as a session transcript.

**Why failed attempts are preserved:** Agent transcripts are kept for both successful and unsuccessful interactions, including prompts that produced incorrect code, code that failed tests, or approaches that had to be abandoned. This is a deliberate choice: a transcript containing only clean, successful generations would misrepresent the actual engineering process and would hide the debugging and judgment that turned a flawed first attempt into a correct final implementation. Preserving failures makes the record honest and pedagogically useful — a reviewer can see not just what was built, but how problems in the generated code were identified and resolved.

**Repository structure for transcripts:**

```
agent_transcripts/
├── session_01_project_setup.md
├── session_02_database.md
├── session_03_api.md
├── session_04_rag.md
├── session_05_frontend.md
├── session_06_testing.md
└── README.md
```

Each `session_XX_*.md` file corresponds to one milestone-scale unit of work from Section 9, and contains the prompts issued, the agent's responses (including any that were rejected or corrected), the reasoning behind accepting or rejecting each attempt, and the final state that was actually merged. `README.md` in this directory explains the numbering scheme and how sessions map to milestones, so the transcript record remains navigable as it grows.

---

## 14. Development Timeline

| Phase | Duration | Dependencies | Output |
|---|---|---|---|
| Project Setup | 3 days | None | Running Docker Compose stack, base apps, tooling configured |
| Database Layer | 4 days | Project Setup | Complete ORM models, initial Alembic migration, seed data |
| REST API | 6 days | Database Layer | All `docs/api_design.md` endpoints implemented and unit-tested |
| LLM Integration | 5 days | REST API | Working provider abstraction for Anthropic, OpenAI, and Ollama |
| RAG Pipeline | 6 days | Database Layer, LLM Integration | Transcript ingestion, embedding, and retrieval working end to end |
| Artifact Generation | 5 days | LLM Integration, RAG Pipeline | Agent workflows producing persisted, grounded artifacts |
| Frontend | 8 days | Artifact Generation | Full UI implementing the primary user workflow |
| Testing | 5 days | Frontend | Coverage targets met, integration and end-to-end suites passing |
| Deployment | 3 days | Testing | Verified production Compose stack and deployment documentation |

*Durations represent focused engineering effort per phase and assume phases are largely sequential given their dependency chain, though early phases of one milestone (e.g., frontend scaffolding) may reasonably begin once its primary dependency is functionally, if not fully, complete.*

---

## 15. Risks and Mitigation

| Risk | Impact | Mitigation |
|---|---|---|
| **Database failures** | Loss of availability or data for all downstream features. | Named volume persistence, regular backup strategy documented in operational runbooks, Alembic migrations kept reversible, health checks gate dependent services from starting against a broken database. |
| **LLM downtime** | Chat, RAG, and artifact generation features degrade or fail. | Provider abstraction (Section 4) allows failover between Anthropic, OpenAI, and Ollama; service layer wraps provider calls with timeouts and clear error surfaces rather than indefinite hangs. |
| **Prompt instability** | Inconsistent or low-quality generated output across runs. | Prompts are version-controlled alongside code, tested against representative inputs during development, and refined iteratively as part of the agent workflow (Section 13) and RAG grounding (Section 9, Milestone 5) rather than left ad hoc. |
| **Docker issues** | Environment inconsistency or failure to start across machines. | Health checks, explicit `depends_on` conditions, and a committed `.env.example` reduce configuration drift; the Compose stack is the single supported way to run the system, eliminating "works on my machine" variance. |
| **Vector database corruption** | Degraded or failed retrieval, breaking RAG-dependent features. | ChromaDB data is bind-mounted to `chroma/` for visibility and backup; `scripts/ingest_transcripts.py` is idempotent and can fully re-populate the index from source transcripts if needed. |
| **API latency** | Poor user experience, particularly around LLM and retrieval calls. | Performance logging (Section 11) on LLM and retrieval operations from day one, async I/O throughout the backend, and a clear path to background processing (Section 16) if synchronous latency becomes unacceptable. |
| **Frontend/backend synchronization** | UI breaks silently when API contracts change. | Shared, explicit schemas (Pydantic on the backend, TypeScript types on the frontend) kept in sync manually against `docs/api_design.md`, with API tests (Section 10) acting as a contract check that catches drift before it reaches the frontend team. |

---

## 16. Future Enhancements

The following are explicitly out of scope for the milestones in Section 9, but the architecture in this plan is designed not to preclude them:

- **Authentication** — a proper user identity and authorization layer, added at the `app/api/deps.py` boundary described in Section 12, enabling multi-user isolation.
- **Streaming Responses** — server-sent events or WebSocket-based streaming of LLM output to the frontend, reducing perceived latency for long generations.
- **Background Workers** — offloading long-running artifact generation to a task queue (e.g., Celery or an async task runner) so API requests remain fast and non-blocking.
- **Redis** — introduced as both a caching layer and a broker for the background worker system above.
- **Caching** — caching frequent RAG retrievals and/or LLM responses for repeated or near-duplicate queries to reduce latency and provider cost.
- **Multi-user Support** — extending the current single-tenant data model to support isolated data per user or organization, building on the authentication layer above.
- **Cloud Deployment** — migrating from single-host Docker Compose to a managed container platform, with managed PostgreSQL and object storage replacing bind-mounted volumes.
- **CI/CD** — automating the test suite (Section 10) and deployment (Section 9, Milestone 9) through a pipeline that runs on every push, rather than being run manually.
- **Observability** — extending the structured logging foundation (Section 11) with metrics collection and distributed tracing once the system has enough moving parts to benefit from it.

---

## 17. Conclusion

This development plan translates the requirements, architecture, database design, and API contracts already defined for The Lenny Growth Assistant into a concrete, ordered, and accountable path to a working system. Its emphasis on modular architecture and SOLID principles keeps the system's three interchangeable AI providers, its persistence layer, and its retrieval pipeline independently changeable — which is what **maintainability** means in practice for a project of this shape. Its incremental, dependency-ordered milestone structure (Section 9), combined with a testing strategy that targets the highest-risk modules (Section 10), is what makes **scalability** and **reliability** achievable outcomes rather than aspirations: the system is verified in working, demonstrable slices rather than assembled all at once and hoped into correctness. Explicit standards for both backend and frontend (Sections 4–5), a disciplined Git workflow (Section 6), and a transparent, fully preserved record of AI-assisted development (Section 13) together constitute the **professional engineering practices** this plan is built around — practices chosen not for their own sake, but because each one directly reduces a specific, identified risk to the project (Section 15). Taken together, this plan gives engineers everything needed to begin implementation immediately, and gives reviewers a clear, honest account of how the system was — and will continue to be — built toward **production readiness**.
