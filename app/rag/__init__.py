"""
RAG (Retrieval-Augmented Generation) package.

Contains the ingestion and retrieval pipeline for the Lenny Podcast
transcript archive: discovering transcript files, parsing frontmatter
metadata, chunking transcript text, generating embeddings, and
storing/querying chunks in ChromaDB. PostgreSQL metadata access goes
through the existing TranscriptService/TranscriptRepository — this
package never issues raw SQLAlchemy queries itself.

Scope: knowledge ingestion and semantic retrieval only. No chat
generation, prompt construction, or LLM completion calls exist here.
"""