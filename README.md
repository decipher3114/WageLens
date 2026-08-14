# WageLens 🎙️

> **Voice-first wage discrepancy evidence platform for gig workers — speak your complaint in Hindi, get structured evidence and spoken feedback in seconds.**

---

## Why We Built This

Millions of gig workers — auto-rickshaw drivers, cab drivers on platforms like Ola and Uber — routinely experience wage discrepancies: the fare shown before a trip doesn't match what they're actually paid. When this happens, most workers have no easy way to document it. Filing a formal complaint requires literacy, access to support channels, and enough English to navigate app interfaces. For a driver finishing a night shift, that bar is simply too high.

**WageLens lowers that bar to a single voice message.**

The problem isn't just individual unfairness — it's systemic. A driver underpaid on a single route at a specific time might be one of hundreds experiencing the same issue. Without aggregation, those signals are invisible. WageLens makes them visible.

### What WageLens Contributes

- **Multilingual voice intake** — drivers speak Hindi (or a mix of Hindi and English); browser-native speech recognition captures it without any app install.
- **Structured evidence extraction** — a four-stage CrewAI pipeline (extraction → verification->pattern detection->spoken feedback) uses an LLM to parse trip facts (route, time, platform, quoted and paid amounts) out of conversational speech, with double-agent validation to reduce errors.
- **Cross-driver pattern detection** — complaints are embedded and stored in Qdrant. Each new complaint is scored against the corpus using a weighted similarity function (location × 0.45 + platform × 0.30 + time × 0.25) to surface recurring route-level discrepancy clusters.
- **Spoken feedback** — Rime TTS reads the outcome back to the driver in plain language, closing the loop even for users who can't read the screen.

---

## Product Demo Video

[![WageLens Demo](https://i.ytimg.com/vi/SvG1HuaTTmQ/maxresdefault.jpg)](https://youtu.be/SvG1HuaTTmQ)

## Product Screenshots

| Landing page | Register a complaint |
|:---:|:---:|
| ![Landing page](assets/screenshots/landing_page.png) | ![Register complaint](assets/screenshots/regsiter_complaint.png) |

| Complaint registered | Dashboard |
|:---:|:---:|
| ![Complaint registered](assets/screenshots/complaint_registered.png) | ![Dashboard](assets/screenshots/dashboard.png) |

---

## Architecture

```
Browser (Next.js 16 / React 19)
  │  Speech → text (Web Speech API)
  │  Text complaint → POST /api/complaints/voice
  ▼
FastAPI Backend (port 8080)
  │
  ├─► [Stage 1] CrewAI Extraction Agent  ──► LLM (GPT-4o-mini / OpenRouter)
  │      Parses Hindi transcript into structured JSON
  │
  ├─► [Stage 2] CrewAI Verification Agent ──► LLM
  │      Cross-checks extraction, lists missing fields
  │
  ├─► [Stage 3] CrewAI Pattern Detection Agent ──► Qdrant Vector Store
  │      Embeds complaint signature, scores weighted similarity, clusters complaints
  │      SQLite persists accepted complaints + cluster IDs
  │
  └─► [Stage 4] Rime TTS  ──► Spoken feedback synthesised → returned to browser
```

### Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16, React 19, Tailwind CSS 4, Web Speech API |
| Backend | FastAPI, Python 3.12, uv |
| AI Orchestration | CrewAI (sequential agent pipeline) |
| LLM | OpenAI GPT-4o-mini (or any OpenRouter model) |
| Vector Store | Qdrant (Docker) + HuggingFace sentence-transformers |
| Text-to-Speech | Rime TTS (speaker: `nadi`, model: `coda`) |
| Database | SQLite (via SQLAlchemy) |

---

## Reproducing the Results

### Prerequisites

| Tool | Version |
|---|---|
| Node.js | 20+ |
| Python | 3.12+ |
| [uv](https://docs.astral.sh/uv/) | latest |
| Docker | any recent version (for Qdrant) |

### API Keys Required

| Key | Where to get it |
|---|---|
| `OPENAI_API_KEY` | [platform.openai.com](https://platform.openai.com) or any [OpenRouter](https://openrouter.ai) key |
| `RIME_API_KEY` | [rime.ai](https://rime.ai) |
| `HF_TOKEN` | [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) |

### Run locally

Follow the setup guides for each service:

- **[Backend](backend/README.md)** — Qdrant, FastAPI, CrewAI pipeline
- **[Frontend](frontend/README.md)** — Next.js app

API: `http://localhost:8080` · App: `http://localhost:3000`

### Test complaint

Navigate to `http://localhost:3000/complaints/new`, click the microphone, and say (in Hindi or English):

> *"Mera trip Sector 12 se Ghaziabad tha. Ola ne ₹220 dikhaya tha, lekin mujhe sirf ₹160 mila. Trip raat 9 baje tha."*

The backend will extract trip facts, check for patterns, and play back a spoken confirmation.

---

## Performance Metrics

### Pattern Detection Scoring

The core pattern-matching algorithm uses a **weighted composite score** across three dimensions:

| Dimension | Weight | Rationale |
|---|---|---|
| Location (route) | **0.45** | Route is the strongest signal — same pickup/drop is the clearest indicator of a systematic issue |
| Platform | **0.30** | Platform identity determines which company's pricing is at fault |
| Time window | **0.25** | Time of day captures surge pricing and shift-change discrepancies |

**Similarity thresholds:**

| Threshold | Value | Meaning |
|---|---|---|
| `QDRANT_PATTERN_THRESHOLD` | `0.65` | Minimum composite score to declare a complaint part of a pattern |
| `QDRANT_MIN_CLUSTER_SIZE` | `2` | Minimum complaints in a cluster to flag as a systemic issue |
| `CLUSTER_JOIN_THRESHOLD` | `0.45` | Minimum score to merge a new complaint into an existing cluster |
| `MATCH_DIMENSION_THRESHOLD` | `0.50` | Minimum score on any single dimension to count a hit as qualifying |

**Why these metrics?**

These thresholds were chosen to minimize false positives (random complaints incorrectly grouped together) while remaining sensitive enough to catch genuine patterns early — even with a small dataset. The location weight is highest because two unrelated complaints on the same route are far more actionable for labor researchers than two complaints at the same time of day on different routes.

### Extraction Quality

The four-stage pipeline (extraction → verification → pattern detection → spoken feedback) catches LLM hallucinations and partial extractions before they enter the database. Only after passing Stage 2 verification — with all six required fields present and internally consistent — does a complaint proceed to Stage 3 pattern detection and Stage 4 TTS feedback:

| Field | Description |
|---|---|
| `trip_time` | 12-hour English time (e.g. "9:00 PM") |
| `pickup_location` | English place name |
| `drop_location` | English place name |
| `quoted_amount` | Fare shown/promised (numeric) |
| `paid_amount` | Fare actually received (numeric) |
| `platform` | Ride-hailing platform (e.g. Ola, Uber) |

Incomplete complaints are **discarded** with spoken feedback telling the driver exactly what information is missing, so they can re-submit with a complete complaint.

---

## API Reference

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/complaints/voice` | `POST` | Submit a complaint transcript, returns `VoiceComplaintResponse` with TTS audio |
| `/api/complaints` | `GET` | List all accepted complaints |
| `/api/dashboard/stats` | `GET` | Dashboard stats: totals, clusters, top patterns |

---

## Main App Routes

| Route | Purpose |
|---|---|
| `/` | Landing page |
| `/complaints/new` | Register a complaint (voice or text) |
| `/dashboard` | Complaint stats and pattern clusters |

---

## Presentation

📎 [Download Slide Deck (.pptx)](assets/presentation/WageLens.pptx)

---

## Credits

WageLens was built with the support of the following amazing partners:

| Partner | Contribution |
|---|---|
| 🤝 **[Pathway](https://pathway.com)** | Real-time data pipeline infrastructure and inspiration |
| 🤝 **[Rime](https://rime.ai)** | Text-to-speech synthesis — giving workers spoken, accessible feedback in their own language |
| 🤝 **[Weya](https://weya.ai)** | Platform support and hackathon partnership |
| 🤝 **[Qdrant](https://qdrant.tech)** | High-performance vector search enabling cross-driver pattern clustering |

---

## License

MIT
