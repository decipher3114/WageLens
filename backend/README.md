# WageLens Backend

FastAPI service for voice complaint intake, CrewAI extraction, Qdrant pattern search, and Rime TTS.

## Setup

```bash
cd backend
cp .env.example .env   # fill in API keys
uv venv
uv sync
```

## Activate the virtual environment

**macOS / Linux**

```bash
source .venv/bin/activate
```

**Windows (PowerShell)**

```powershell
.venv\Scripts\Activate.ps1
```

**Windows (cmd)**

```cmd
.venv\Scripts\activate.bat
```

## Run

```bash
uv run dev
```

`uv run dev` starts Qdrant with `docker compose up -d`, runs the API on port 8080, and runs `docker compose down` when you press Ctrl+C.

You can use `uv run dev` without activating the venv; activation is optional if you prefer a traditional shell workflow.

API: `http://localhost:8080`

## Environment

See [`.env.example`](.env.example) for all variables. Required keys:

- `RIME_API_KEY`
- `OPENAI_API_KEY` (OpenAI or OpenRouter)
- `HF_TOKEN`

Back to [project README](../README.md).
