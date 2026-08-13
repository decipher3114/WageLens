# WageLens

Voice-first wage discrepancy reporting for gig workers. Drivers speak (or type) complaints in Hindi; the backend extracts trip facts, detects recurring route patterns, and returns spoken feedback.


## Presentation

### [Presentation File (.pptx)](assets/presentation/WageLens.pptx)

## Stack

FastAPI, CrewAI agents, SQLite, Qdrant (pattern clustering), Rime TTS

## Prerequisites

- Python 3.12+ with [uv](https://docs.astral.sh/uv/)
- Docker (for Qdrant)
- API keys: OpenAI (or OpenRouter), Rime, Hugging Face (for embeddings)

## Run locally

Follow the setup guides for each service:

- **[Backend](backend/README.md)** — Qdrant, FastAPI, CrewAI pipeline


API: `http://localhost:8080`
