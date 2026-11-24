# Lyftr AI Chatbot

A full-stack AI chatbot built with React, FastAPI, SQLite, LiteLLM, and Google Gemini.

The application supports multi-turn conversations, response caching, automatic API-key failover, token/latency metadata, Docker-based local development, and failure simulation.

## Features

- Multi-turn AI conversations
- Google Gemini integration through LiteLLM
- SQLite conversation history
- 10-minute in-memory LLM response cache
- Automatic failover across multiple API keys
- Simulated provider failures for testing
- Input and output token tracking
- Request latency tracking
- Per-response inference metadata
- React frontend
- FastAPI backend
- Docker Compose support
- Automated backend tests

## Architecture

```text
Browser
   |
   v
React Frontend
localhost:3000
   |
   | HTTP / JSON
   v
FastAPI Backend
localhost:8000
   |
   +------> SQLite
   |        Conversation history
   |
   +------> In-memory TTL cache
   |
   +------> LiteLLM
               |
               +--> Gemini API Key 1
               |
               +--> Gemini API Key 2
                    (automatic failover)
```

## Project Structure

```text
lyftr-ai-assignment/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── database.py
│   │   ├── llm.py
│   │   ├── main.py
│   │   └── schemas.py
│   ├── tests/
│   │   └── test_llm.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── App.css
│   │   └── index.css
│   ├── Dockerfile
│   └── package.json
├── .env.example
├── .gitignore
├── docker-compose.yml
├── Makefile
└── README.md
```

## Environment Variables

Copy the example environment configuration:

```bash
cp .env.example backend/.env
```

Then edit `backend/.env`:

```env
LLM_API_KEYS=your_gemini_api_key_1,your_gemini_api_key_2
DATABASE_URL=sqlite:///./app.db
ALLOWED_ORIGINS=http://localhost:3000
ENABLE_FAILURE_SIMULATION=true
LLM_MODEL=gemini/gemini-3.5-flash-lite
```

`LLM_API_KEYS` accepts comma-separated Gemini API keys.

Real API keys must never be committed to Git.

## Run with Docker

Make sure Docker Desktop is running.

From the project root:

```bash
make up
```

The services will be available at:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`
- Swagger API documentation: `http://localhost:8000/docs`
- Health endpoint: `http://localhost:8000/health`

Stop the application with:

```bash
make down
```

## Run Without Docker

### Backend

```bash
cd backend

python3 -m venv venv
source venv/bin/activate

python -m pip install -r requirements.txt

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

### Frontend

In another terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite development frontend runs at:

```text
http://localhost:5173
```

## API

### Health

```http
GET /health
```

Example response:

```json
{
  "status": "ok",
  "keys_configured": 2,
  "cache_enabled": true
}
```

### Chat

```http
POST /chat
```

Example request:

```json
{
  "session_id": "example-session",
  "message": "Hello"
}
```

Example response:

```json
{
  "session_id": "example-session",
  "reply": "Hello! How can I help you?",
  "metadata": {
    "resolution_source": "LIVE_INFERENCE",
    "model": "gemini/gemini-3.5-flash-lite",
    "latency_ms": 1200,
    "input_tokens": 10,
    "output_tokens": 8,
    "key_id": "key_1",
    "fallback_attempts": 0
  }
}
```

### Session Messages

```http
GET /sessions/{session_id}/messages
```

Returns the stored conversation history for a session.

## Response Caching

Successful LLM responses are cached for 10 minutes.

The cache key is generated from:

- Model
- System prompt
- Full conversation history
- Current user message

A live request reports:

```text
resolution_source = LIVE_INFERENCE
```

A cache hit reports:

```text
resolution_source = LLM_CACHE
```

Cache hits preserve the token usage associated with the original response while returning:

```text
key_id = null
fallback_attempts = 0
```

## API Key Failover

API keys are attempted sequentially.

If a provider returns a retryable failure such as HTTP `429` or `5xx`, the backend automatically attempts the next configured API key.

The response metadata reports:

```text
key_id
fallback_attempts
```

If every configured provider fails, the API returns HTTP `503` with:

```json
{
  "detail": "all providers unavailable"
}
```

## Failure Simulation

Failure simulation can be enabled with:

```env
ENABLE_FAILURE_SIMULATION=true
```

The `/chat` endpoint accepts the `X-Simulate-Failure` header.

Example:

```text
X-Simulate-Failure: key_1=429
```

This forces the first key to fail and allows the failover path to be tested.

To simulate all providers failing:

```text
X-Simulate-Failure: *=503
```

## Tests

Backend tests use mocked LLM responses and therefore do not consume Gemini API quota.

Run:

```bash
cd backend
source venv/bin/activate
python -m pytest -v
```

Current test coverage includes:

- Deterministic cache keys
- Live inference metadata
- Cache-hit behavior
- Cached token usage preservation
- API-key failover
- All-provider failure
- Failure-simulation parsing

Expected result:

```text
7 passed
```

## Docker

Both backend and frontend use multi-stage Docker builds.

Useful commands:

```bash
make up
make down
make build
make logs
make ps
make restart
```

## Security

The following files are intentionally excluded from Git:

```text
backend/.env
*.db
venv/
node_modules/
```

API credentials must only be supplied through environment variables.

## Technology Stack

**Frontend**

- React
- Vite
- CSS

**Backend**

- Python
- FastAPI
- LiteLLM
- Google Gemini
- SQLite
- cachetools

**Infrastructure**

- Docker
- Docker Compose
- Nginx
- Make

## Deployment

Deployment URLs will be added here after the frontend and backend are deployed.

- Frontend: TBD
- Backend: TBD