import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.database import Message, create_tables, get_db
from app.schemas import ChatRequest
from app.llm import (
    AllProvidersUnavailable,
    generate_reply,
    get_key_count,
    is_cache_enabled,
)


# ---------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------

DEFAULT_SYSTEM_PROMPT = "You are a helpful assistant."


# ---------------------------------------------------------
# APPLICATION LIFESPAN
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    yield


# ---------------------------------------------------------
# FASTAPI APPLICATION
# ---------------------------------------------------------

app = FastAPI(
    title="Lyftr AI Chatbot API",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------
# CORS
# ---------------------------------------------------------

allowed_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
    "https://lyftr-ai-frontend-99eu.onrender.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# HEALTH ENDPOINT
# ---------------------------------------------------------

@app.get("/health")
def health():
    return {
        "status": "ok",
        "keys_configured": get_key_count(),
        "cache_enabled": is_cache_enabled(),
    }


# ---------------------------------------------------------
# CHAT ENDPOINT
# ---------------------------------------------------------

@app.post("/chat")
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    x_simulate_failure: str | None = Header(
        default=None,
        alias="X-Simulate-Failure",
    ),
):
    """
    Multi-turn chat endpoint.

    Features:
    - SQLite conversation history
    - Optional custom system prompt
    - LLM response caching
    - API-key failover
    - Failure simulation
    - Token tracking
    - Latency tracking
    """

    # -----------------------------------------------------
    # LOAD EXISTING SESSION HISTORY
    # -----------------------------------------------------

    previous_messages = (
        db.query(Message)
        .filter(Message.session_id == request.session_id)
        .order_by(Message.id.asc())
        .all()
    )

    messages = []

    # -----------------------------------------------------
    # SYSTEM PROMPT
    # -----------------------------------------------------

    system_prompt = (
        request.system_prompt
        if request.system_prompt
        else DEFAULT_SYSTEM_PROMPT
    )

    messages.append(
        {
            "role": "system",
            "content": system_prompt,
        }
    )

    # -----------------------------------------------------
    # ADD PREVIOUS CONVERSATION
    # -----------------------------------------------------

    for previous_message in previous_messages:
        messages.append(
            {
                "role": previous_message.role,
                "content": previous_message.content,
            }
        )

    # -----------------------------------------------------
    # ADD CURRENT USER MESSAGE
    # -----------------------------------------------------

    messages.append(
        {
            "role": "user",
            "content": request.message,
        }
    )

    # -----------------------------------------------------
    # CALL LLM
    # -----------------------------------------------------

    start_time = time.perf_counter()

    try:
        result = generate_reply(
            messages,
            simulate_failure=x_simulate_failure,
        )

    except AllProvidersUnavailable:
        raise HTTPException(
            status_code=503,
            detail="all providers unavailable",
        )

    latency_ms = int(
        (time.perf_counter() - start_time) * 1000
    )

    reply = result["reply"]

    # -----------------------------------------------------
    # SAVE USER MESSAGE
    # -----------------------------------------------------

    user_message = Message(
        session_id=request.session_id,
        role="user",
        content=request.message,
    )

    db.add(user_message)

    # -----------------------------------------------------
    # SAVE ASSISTANT MESSAGE
    # -----------------------------------------------------

    assistant_message = Message(
        session_id=request.session_id,
        role="assistant",
        content=reply,
    )

    db.add(assistant_message)

    db.commit()

    # -----------------------------------------------------
    # RETURN RESPONSE
    # -----------------------------------------------------

    return {
        "session_id": request.session_id,
        "reply": reply,
        "metadata": {
            "resolution_source": result["resolution_source"],
            "model": result["model"],
            "latency_ms": latency_ms,
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "key_id": result["key_id"],
            "fallback_attempts": result["fallback_attempts"],
        },
    }


# ---------------------------------------------------------
# GET SESSION HISTORY
# ---------------------------------------------------------

@app.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
):
    """
    Return all messages belonging to a session.
    """

    messages = (
        db.query(Message)
        .filter(Message.session_id == session_id)
        .order_by(Message.id.asc())
        .all()
    )

    if not messages:
        raise HTTPException(
            status_code=404,
            detail="session not found",
        )

    return {
        "session_id": session_id,
        "messages": [
            {
                "role": message.role,
                "content": message.content,
            }
            for message in messages
        ],
    }