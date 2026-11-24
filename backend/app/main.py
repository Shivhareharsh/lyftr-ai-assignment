import json
import os
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
# APPLICATION STARTUP
# ---------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create SQLite tables automatically
    create_tables()
    yield


# ---------------------------------------------------------
# FASTAPI APPLICATION
# ---------------------------------------------------------

app = FastAPI(
    title="Lyftr AI Chatbot API",
    version="1.0.0",
    lifespan=lifespan
)


# ---------------------------------------------------------
# CORS CONFIGURATION
# ---------------------------------------------------------

allowed_origins = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173"
    ).split(",")
    if origin.strip()
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
        "cache_enabled": is_cache_enabled()
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
        alias="X-Simulate-Failure"
    )
):
    # -----------------------------------------------------
    # 1. Load previous conversation history from SQLite
    # -----------------------------------------------------

    history = (
        db.query(Message)
        .filter(
            Message.session_id == request.session_id
        )
        .order_by(Message.id.asc())
        .all()
    )

    # -----------------------------------------------------
    # 2. Build complete conversation for Gemini
    # -----------------------------------------------------

    messages = [
        {
            "role": "system",
            "content": (
                request.system_prompt
                or DEFAULT_SYSTEM_PROMPT
            )
        }
    ]

    # Add previous conversation messages
    for item in history:
        messages.append({
            "role": item.role,
            "content": item.content
        })

    # Add current user message
    messages.append({
        "role": "user",
        "content": request.message
    })

    # -----------------------------------------------------
    # 3. Start latency timer
    # -----------------------------------------------------

    start_time = time.perf_counter()

    try:
        llm_result = generate_reply(
            messages,
            simulate_failure=x_simulate_failure
        )

    except AllProvidersUnavailable:
        # IMPORTANT:
        # Failed requests are NOT stored in SQLite.
        raise HTTPException(
            status_code=503,
            detail="all providers unavailable"
        )

    latency_ms = int(
        (time.perf_counter() - start_time) * 1000
    )

    # -----------------------------------------------------
    # 4. Build metadata
    # -----------------------------------------------------

    metadata = {
        "resolution_source": llm_result[
            "resolution_source"
        ],
        "model": llm_result["model"],
        "latency_ms": latency_ms,
        "input_tokens": llm_result[
            "input_tokens"
        ],
        "output_tokens": llm_result[
            "output_tokens"
        ],
        "key_id": llm_result["key_id"],
        "fallback_attempts": llm_result[
            "fallback_attempts"
        ]
    }

    # -----------------------------------------------------
    # 5. Save USER message
    # -----------------------------------------------------

    user_message = Message(
        session_id=request.session_id,
        role="user",
        content=request.message
    )

    db.add(user_message)

    # -----------------------------------------------------
    # 6. Save ASSISTANT message
    # -----------------------------------------------------

    assistant_message = Message(
        session_id=request.session_id,
        role="assistant",
        content=llm_result["reply"],
        metadata_json=json.dumps(metadata)
    )

    db.add(assistant_message)

    # Save both messages
    db.commit()

    # -----------------------------------------------------
    # 7. Return response
    # -----------------------------------------------------

    return {
        "session_id": request.session_id,
        "reply": llm_result["reply"],
        "metadata": metadata
    }


# ---------------------------------------------------------
# SESSION HISTORY ENDPOINT
# ---------------------------------------------------------

@app.get("/sessions/{session_id}/messages")
def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db)
):
    messages = (
        db.query(Message)
        .filter(
            Message.session_id == session_id
        )
        .order_by(Message.id.asc())
        .all()
    )

    # Unknown session → 404
    if not messages:
        raise HTTPException(
            status_code=404,
            detail="session not found"
        )

    result = []

    for message in messages:

        item = {
            "role": message.role,
            "content": message.content
        }

        # Include metadata for assistant messages
        if (
            message.role == "assistant"
            and message.metadata_json
        ):
            item["metadata"] = json.loads(
                message.metadata_json
            )

        result.append(item)

    return {
        "session_id": session_id,
        "messages": result
    }