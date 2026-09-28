# Persnol Chat Agent

A self-hosted WhatsApp AI agent that reads and replies like a person — in whatever language you write in.

It runs on your own machine, connects to WhatsApp via QR scan, and handles **text**, **voice notes**, and **images** through a mix of Groq and Gemini models, with a browser dashboard to watch it live.

> **Note:** The system prompt is deliberately tuned to reply as a human rather than an assistant (see `core_agent/system_prompt.py`). Use this only on accounts and in scenarios where you are authorized to do so, and be aware that automated WhatsApp use is against the WhatsApp Terms of Service.

---

## Features

| | |
|---|---|
| **Multilingual replies** | Auto-detects the sender's language *and* script (Urdu, Roman Urdu, English, Pashto, Arabic) and replies in the exact same one |
| **Voice notes** | Transcribes audio with Whisper `large-v3-turbo`, then replies to the spoken text |
| **Images** | Sends photos to Gemini 1.5 Flash Vision with the sender's caption as context |
| **Model fallback chain** | Tries three Groq models in order, then falls back to Gemini if all fail — a bad model or rate limit won't kill the agent |
| **Live dashboard** | Connection status, QR scan, real-time message logs, and a test playground |
| **Human-like pacing** | Random 2–4s think time and "composing…" presence before each reply |

---

## Architecture

Two processes that talk over HTTP on `localhost:8000`:

```
┌────────────────────────┐         ┌──────────────────────────────┐
│   whatsapp-gateway/    │  POST   │        core_agent/           │
│    (Node.js + Baileys) │────────▶│      (Python + FastAPI)      │
│                        │◀────────│                              │
│  • Holds WhatsApp login│  {reply}│  • Groq  → text replies      │
│  • Receives messages   │         │  • Whisper → transcription    │
│  • Sends the reply     │         │  • Gemini → vision            │
└────────────────────────┘         └──────────────┬───────────────┘
                                    serves dashboard.html
                                                 │
                                    ┌────────────▼───────────────┐
                                    │   dashboard.html (:8000)   │
                                    └────────────────────────────┘
```

The gateway never talks to an AI model itself. It authenticates with WhatsApp, forwards the message payload, and sends back whatever the Python side replies with.

---

## Requirements

- **Python 3.10+**
- **Node.js 18+**
- A **Groq API key** — <https://console.groq.com/keys>
- A **Gemini API key** — <https://aistudio.google.com/app/apikey>

---

## Setup

### 1. Clone

```bash
git clone https://github.com/aiengineertahir/persnol-chat-agent-.git
cd persnol-chat-agent-
```

### 2. Configure API keys

```bash
cp .env.example .env
```

Edit `.env` and paste your keys:

```env
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AIza...
```

`.env` is git-ignored and must never be committed.

### 3. Create the temp media directory

The backend writes incoming audio and images to disk before processing them, so this folder has to exist:

```bash
mkdir temp_downloads
```

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 5. Install Node dependencies

```bash
cd whatsapp-gateway
npm install
```

---

## Running

Open **two terminals**.

**Terminal 1 — Python backend** (must be started from inside `core_agent/`, because `ai_engine.py` uses a same-directory import):

```bash
cd core_agent
uvicorn main:app --reload --port 8000
```

**Terminal 2 — WhatsApp gateway:**

```bash
cd whatsapp-gateway
node index.js
```

A QR code will be generated in the terminal and pushed to the dashboard.

### 3. Scan and connect

Open <http://localhost:8000/dashboard>, scan the QR code with WhatsApp on your phone (**Settings → Linked Devices**), and the header will flip to **CONNECTED**.

Session credentials are cached in `whatsapp-gateway/auth_info_baileys/`, so you only scan once. Delete that folder to force a re-scan.

---

## Dashboard

Served at <http://localhost:8000/dashboard>:

- **Connection panel** — live status and QR code
- **Message logs** — every inbound message and the reply sent back, with the message type
- **Test playground** — send a message through the AI engine without WhatsApp, useful for tuning replies
- **Clear / delete logs** — in-memory only, resets on server restart

---

## API

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/` , `/dashboard` | Serve the dashboard |
| `GET` | `/api/status` | Connection status, QR data, logs |
| `POST` | `/api/update-status` | Called by the gateway to report state |
| `POST` | `/api/test-chat` | Generate a reply without WhatsApp |
| `GET` `POST` | `/api/logs/delete/{id}` | Delete one log entry |
| `POST` | `/api/logs/clear` | Clear all logs |
| `POST` | `/whatsapp-webhook` | Inbound message endpoint used by the gateway |

Inbound payload accepted by `/whatsapp-webhook`:

```json
{
  "sender": "Ahmed",
  "type": "audio",
  "text": "",
  "mediaB64": "<base64>"
}
```

Responds with `{ "reply": "..." }`.

---

## Models

| Task | Model |
|---|---|
| Text (tried in order) | `openai/gpt-oss-20b` → `qwen/qwen3.6-27b` → `allam-2-7b` |
| Text fallback | `gemini-1.5-flash` |
| Voice transcription | `whisper-large-v3-turbo` |
| Image understanding | `gemini-1.5-flash` |

To change models, edit `core_agent/ai_engine.py:16` and the model names at lines 38 and 57.

Reasoning tags (`<think>…</think>`) are stripped from Groq responses before they are sent, so the sender never sees model scratch-work.

---

## Project structure

```
persnol-chat-agent/
├── .env.example          # API key template
├── dashboard.html         # Control center UI (Tailwind via CDN)
├── requirements.txt
├── core_agent/            # Python + FastAPI backend
│   ├── ai_engine.py       # Groq / Whisper / Gemini calls
│   ├── main.py            # FastAPI app, webhooks, log state
│   └── system_prompt.py   # Persona + language rules
├── whatsapp-gateway/      # Node.js + Baileys gateway
│   └── index.js           # WhatsApp connection, QR, message relay
└── temp_downloads/        # Scratch dir for media (create it yourself)
```

---

## Customizing the personality

Everything the agent says is driven by `core_agent/system_prompt.py`. Edit `SYSTEM_PROMPT` and restart the backend — no other changes needed.

```python
SYSTEM_PROMPT = """
You are acting as a real human on WhatsApp.

Rules:
1. Detect the user's input language and ALWAYS reply in the EXACT same language and script.
2. Keep replies natural, short, and casual.
...
"""
```

---

## Troubleshooting

**`ModuleNotFoundError: No module named 'system_prompt'`**
You started `uvicorn` from the repo root. Run it from inside `core_agent/`.

**Audio/image messages fail silently**
`temp_downloads/` doesn't exist. Create it and restart the backend.

**Dashboard says `DISCONNECTED` and no QR appears**
The gateway isn't running, or the backend isn't up on port 8000. Check terminal 1 for a startup error.

**QR won't scan**
Regenerate it: stop the gateway, delete `whatsapp-gateway/auth_info_baileys/`, and run `node index.js` again.

**All replies fall back to the Gemini path**
Your `GROQ_API_KEY` is likely invalid, expired, or out of quota. The agent still works, but you'll lose the primary model.

**Replies look robotic or switch to English**
Loosen rule 1 in `SYSTEM_PROMPT` — the language lock is strict by design.

---

## License

ISC — as declared in `package.json`. No `LICENSE` file has been added yet; add one before publishing.
