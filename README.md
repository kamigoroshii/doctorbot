# DoctorBot

DoctorBot is a Telegram-based prescription assistant.
It accepts prescription images or documents, extracts medication details, checks safety warnings, and sends reminder-ready schedules.

## What This Project Uses

- Python 3.11 (recommended)
- FastAPI + Uvicorn for the backend API
- python-telegram-bot for Telegram integration
- OCR pipeline with Tesseract + OpenCV
- Hybrid prescription entity extraction for Drug / Dose / Frequency / Duration from OCR text
- Built-in multilingual replies with auto language detection
- Voice note transcription with SpeechRecognition
- Text-to-speech audio replies with `/speak`
- AI provider via environment selection:
  - `grok` with `GROK_API_KEY`
  - `openrouter` with `OPENROUTER_API_KEY`
  - `gemini` with `GOOGLE_API_KEY`
  - `demo` mode (no external AI key)
- SQLite database (`doctorbot.db` by default)
- Optional Docker Compose stack (backend + bot + n8n)

## Repository Layout

```
backend/                  FastAPI app, services, DB models
bot/                      Telegram bot handlers and integrations
data/                     Sample/input data
frontend/                 Static frontend file
workflows/                n8n workflow JSON
main.py                   Main launcher (backend|bot|all)
setup.py                  One-time setup (env template + DB init)
start_doctorbot.py        Startup helper with config checks
docker-compose.yml        Optional containerized stack
Dockerfile                Container image definition
```

## Before You Start

1. Install Python 3.11.
2. Install Tesseract OCR on your OS.
3. Create a Telegram bot token from `@BotFather`.
4. Choose an AI provider and create the corresponding API key.

### Install Tesseract (Windows)

Install Tesseract OCR and ensure `tesseract.exe` is available in PATH.

Typical verify command:

```powershell
tesseract --version
```

If this command fails, OCR features will not work until Tesseract is installed correctly.

## Local Setup (Recommended for Your Friend)

Run these commands in project root:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Create env file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` and set at minimum:

```env
TELEGRAM_BOT_TOKEN=<your_telegram_token>
AI_PROVIDER=grok
GROK_API_KEY=<your_grok_key>

# Optional but recommended defaults
DATABASE_URL=sqlite:///./doctorbot.db
API_HOST=0.0.0.0
API_PORT=8000
```

If you use another provider, set:

- `AI_PROVIDER=openrouter` and `OPENROUTER_API_KEY=...`
- `AI_PROVIDER=gemini` and `GOOGLE_API_KEY=...`
- `AI_PROVIDER=demo` for no external AI key

Initialize project:

```powershell
python setup.py
```

## Run Modes

### Full system (backend + bot)

```powershell
python main.py all
```

This starts the API first, waits for health check, then starts the Telegram bot.

### Backend only

```powershell
python main.py backend
```

### Bot only

```powershell
python main.py bot
```

For bot-only mode, make sure backend is already running and reachable through `API_BASE_URL`.

## Health and Connectivity Checks

When backend is running:

- `GET /` should return a running message.
- `GET /health` should return API and AI provider status.

Example:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/health
```

## API Endpoints

- `GET /` basic service status
- `GET /health` backend + AI provider health
- `POST /process-prescription` upload image prescription
- `POST /process-document` upload PDF/DOC/DOCX/TXT/image document

The API response now also includes:

- `extraction_method` to show whether the hybrid extractor or fallback parser was used
- `extraction_confidence` for the hybrid extractor
- `extraction_summary` with the raw entity candidates

## Optional: Docker Compose

Run all configured services:

```powershell
docker compose up --build
```

Included services:

- `doctorbot-backend` on port `8000`
- `doctorbot-bot` linked to backend service
- `n8n` on port `5678` (default basic auth in compose file)

Stop stack:

```powershell
docker compose down
```

## Common Issues

1. Missing env vars at startup:
   - Check `.env` values and selected `AI_PROVIDER`.
2. OCR not reading images:
   - Confirm Tesseract installation and PATH.
3. Bot starts but cannot process files:
   - Verify backend is running and `API_BASE_URL` is correct.
4. AI key errors in bot replies:
   - Check API key validity/credits for selected provider.

## Quick Share Checklist (For GitHub Handoff)

Before sending to your friend, confirm:

1. `.env` is NOT committed.
2. `.env.example` is committed.
3. README is committed.
4. Your friend has Python + Tesseract installed.
5. Your friend has Telegram token + AI key.

## Medical Disclaimer

This project is an informational assistant and does not replace professional medical advice, diagnosis, or treatment.
Always consult a qualified healthcare professional for medical decisions.