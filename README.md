# 🚀 Lenny Growth Assistant

An AI-powered podcast assistant that enables users to search, explore, and interact with knowledge extracted from **Lenny's Podcast** transcripts using **Retrieval-Augmented Generation (RAG)**.

The application ingests podcast transcripts, generates semantic embeddings, stores them in ChromaDB, and answers natural language questions using either a local or cloud Large Language Model (LLM).

---

# ✨ Features

## 🤖 AI Chat Assistant

- Chat with Lenny's Podcast knowledge
- Natural language question answering
- Context-aware responses
- Session-based conversations
- Persistent conversation history

---

## 🔍 Retrieval-Augmented Generation (RAG)

- Semantic transcript search
- Transcript chunking
- Vector embeddings
- ChromaDB vector database
- Prompt engineering
- Context-aware retrieval

---

## 📚 Podcast Knowledge

- Episode discovery
- Guest search
- Episode summaries
- Topic search
- Product management insights
- Growth strategies
- Startup discussions
- AI-related conversations

---

## 💬 Chat Experience

- ChatGPT-like interface
- Markdown rendering
- Code block support
- Typing indicator
- Error handling
- Empty state UI
- Responsive layout

---

## 📖 Rich Responses

- Citations
- Source attribution
- Artifact panel
- Markdown support
- Multi-turn conversations

---

## ⚙️ AI Providers

Supports both:

- 🖥️ Ollama (Local LLM)
- ☁️ OpenAI

Embedding Model

- nomic-embed-text

---

# 🏗️ System Architecture

```
                    User
                      │
                      ▼
              React + Vite Frontend
                      │
                      ▼
                FastAPI Backend
                      │
                      ▼
                Chat Orchestrator
                      │
      ┌───────────────┴────────────────┐
      │                                │
      ▼                                ▼
 Conversation History          Retriever (RAG)
      │                                │
      ▼                                ▼
 PostgreSQL                   ChromaDB Vector Store
                                       │
                                       ▼
                            Relevant Transcript Chunks
                                       │
                                       ▼
                              Prompt Builder
                                       │
                                       ▼
                              Ollama / OpenAI
                                       │
                                       ▼
                                 AI Response
```

---

# 🧠 RAG Pipeline

```
Podcast Transcript

        │

        ▼

Transcript Parser

        │

        ▼

Chunk Generator

        │

        ▼

Embedding Model
(nomic-embed-text)

        │

        ▼

ChromaDB

        │

        ▼

Semantic Retriever

        │

        ▼

Prompt Builder

        │

        ▼

Large Language Model

        │

        ▼

Generated Answer
```

---

# 🛠️ Tech Stack

## Backend

- Python 3.11
- FastAPI
- SQLAlchemy
- PostgreSQL
- ChromaDB
- Ollama
- OpenAI
- Pydantic
- Loguru

---

## Frontend

- React
- TypeScript
- Vite
- Tailwind CSS
- Zustand
- TanStack Query
- Axios
- React Router
- React Markdown
- Sonner

---

# 📂 Project Structure

```
Lenny-Growth-Assistant
│
├── backend
│   ├── app
│   │   ├── api
│   │   ├── chat
│   │   ├── core
│   │   ├── database
│   │   ├── models
│   │   ├── rag
│   │   ├── repositories
│   │   ├── services
│   │   ├── utils
│   │   └── main.py
│   │
│   ├── scripts
│   ├── tests
│   └── requirements.txt
│
├── frontend
│   ├── src
│   │   ├── api
│   │   ├── components
│   │   ├── hooks
│   │   ├── pages
│   │   ├── providers
│   │   ├── routes
│   │   ├── stores
│   │   ├── styles
│   │   └── types
│   │
│   └── package.json
│
├── episodes
├── chroma_data
├── README.md
└── DESIGN.md
```

---

# 💾 Database Design

## PostgreSQL

Stores

- Sessions
- Messages
- Transcript Metadata
- Chat History

---

## ChromaDB

Stores

- Transcript Embeddings
- Transcript Chunks
- Episode Metadata
- Semantic Search Index

---

# ⚡ Installation

## 1. Clone Repository

```bash
git clone <repository-url>

cd lenny-growth-assistant
```

---

# Backend Setup

## Create Virtual Environment

```bash
cd backend

python -m venv .venv
```

Windows

```bash
.venv\Scripts\activate
```

Linux / macOS

```bash
source .venv/bin/activate
```

---

## Install Dependencies

```bash
pip install -r requirements.txt
```

---

## Configure Environment

Create

```
backend/.env
```

```env
DATABASE_URL=postgresql://username:password@localhost:5432/lenny

DEFAULT_PROVIDER=ollama

OLLAMA_BASE_URL=http://localhost:11434

OPENAI_API_KEY=

CHROMA_PERSIST_DIRECTORY=./chroma_data

CHROMA_COLLECTION_NAME=lenny_transcripts
```

---

## Start Backend

```bash
uvicorn app.main:app --reload
```

Backend

```
http://localhost:8000
```

Swagger

```
http://localhost:8000/docs
```

---

# Frontend Setup

```bash
cd frontend

npm install
```

Create

```
frontend/.env
```

```env
VITE_API_BASE_URL=http://localhost:8000
```

Run

```bash
npm run dev
```

Frontend

```
http://localhost:5173
```

---

# Transcript Ingestion

Place transcripts inside

```
episodes/

    episode-name/

        transcript.md
```

Run

```bash
python scripts/ingest_transcripts.py
```

This performs

- Parse transcript
- Generate chunks
- Generate embeddings
- Store metadata
- Store vectors in ChromaDB

---

# REST API

## Sessions

Create Session

```
POST /api/v1/sessions
```

List Sessions

```
GET /api/v1/sessions
```

Delete Session

```
DELETE /api/v1/sessions/{id}
```

---

## Messages

Send Message

```
POST /api/v1/sessions/{id}/messages
```

Get Messages

```
GET /api/v1/sessions/{id}/messages
```

---

## Health

```
GET /health
```

---

# Example Questions

### Episode Search

- List all Elena Verna episodes
- Show me AI-related podcast episodes
- Which guests appeared multiple times?
- Give me Marty Cagan's podcast episodes

---

### Summaries

- Summarize Elena Verna's AI Growth Playbook
- Summarize Product-Led Sales
- Summarize Marty Cagan's product philosophy

---

### Product Management

- What is Product Management?
- What is Product-Led Growth?
- What is Product-Market Fit?
- What makes a great Product Manager?

---

### Growth

- What growth tactics does Elena Verna recommend?
- Give me startup growth advice.
- What mistakes should startups avoid?

---

### AI

- Which episodes discuss AI?
- What is the AI Growth Playbook?
- Find episodes discussing AI agents.

---

# Screenshots

Add screenshots of

- Home Page
- Chat Interface
- Sidebar
- Citation Panel
- Artifact Panel
- Settings Drawer

---

# Future Improvements

- Streaming LLM responses
- Hybrid Search (BM25 + Vector Search)
- Cross-episode summarization
- Citation highlighting
- Authentication
- User profiles
- Multi-modal support
- Redis caching
- Reranking models
- Evaluation pipeline

