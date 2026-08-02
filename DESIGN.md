
---

# DESIGN.md

````md
# Lenny Growth Assistant

## Overview

The Lenny Growth Assistant is an AI-powered Retrieval-Augmented Generation (RAG) application that allows users to interact with Lenny's Podcast transcripts using natural language.

The system indexes transcript embeddings into ChromaDB while storing structured metadata inside PostgreSQL.

---

# High Level Architecture

Frontend

↓

FastAPI

↓

Retriever

↓

ChromaDB

↓

Prompt Builder

↓

LLM

↓

Response

---

# Components

## Frontend

Responsible for

- Chat UI
- Session Management
- Markdown Rendering
- Citations
- Artifact Panel
- Settings

Built using

- React
- TypeScript
- Zustand
- React Query

---

## Backend

Responsible for

- API
- Session Management
- Retrieval
- Prompt Building
- LLM Integration
- Persistence

---

# RAG Flow

## 1

Transcript Loader

Loads transcript.md

↓

## 2

Parser

Extracts

- title
- guest
- description
- youtube url
- transcript body

↓

## 3

Chunker

Splits transcript

↓

## 4

Embedding

Creates embeddings using

nomic-embed-text

↓

## 5

Vector Store

Stores chunks inside ChromaDB

↓

## 6

Retriever

Embeds user query

Searches ChromaDB

Returns Top K chunks

↓

## 7

Prompt Builder

Combines

Conversation History

+

Retrieved Chunks

+

User Question

↓

## 8

LLM

Generates answer

↓

## 9

Frontend

Displays

Markdown

Citations

Artifacts

---

# Backend Layers

API

↓

Orchestrator

↓

Retriever

↓

Prompt Builder

↓

LLM

↓

Repositories

↓

Database

---

# Prompt Structure

System Prompt

Conversation History

Relevant Transcript Knowledge

Current User Question

---

# Session Flow

User creates session

↓

Session stored in PostgreSQL

↓

Messages stored

↓

Conversation History loaded

↓

Prompt constructed

↓

LLM called

↓

Assistant response stored

---

# Vector Store

Database

ChromaDB

Stores

- embedding
- chunk text
- transcript id
- title
- guest
- youtube url

---

# PostgreSQL

Stores

Sessions

Messages

Transcript Metadata

---

# Retrieval

Semantic Search

Top K

Default

5 chunks

Embedding Model

nomic-embed-text

---

# LLM Providers

Supported

Ollama

OpenAI

---

# Error Handling

Validation Errors

Database Errors

Embedding Errors

Vector Store Errors

LLM Errors

Prompt Errors

---

# Logging

Structured logging using Loguru

Logs

- ingestion
- retrieval
- prompt building
- llm latency
- api requests

---

# Design Decisions

Why ChromaDB?

Simple local vector DB

Fast semantic retrieval

Easy persistence

---

Why PostgreSQL?

Reliable relational storage

Chat history

Metadata

---

Why FastAPI?

Fast

Typed

Async support

Automatic OpenAPI

---

Why React?

Component architecture

Fast rendering

Type safety

---

# Future Work

Streaming

Authentication

Hybrid Retrieval

Reranking

Multi-modal support

Redis caching

Conversation memory optimization

Evaluation pipeline

Agent workflow
