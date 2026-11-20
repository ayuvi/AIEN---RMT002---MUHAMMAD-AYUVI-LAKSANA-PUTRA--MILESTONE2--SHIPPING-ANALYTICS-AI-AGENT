
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from src.auth import get_current_user
from src.agent import run_agent
from src.conversations import (
    init_db,
    create_conversation,
    list_conversations,
    get_conversation,
    save_exchange,
)


# ==========================================
# 1. LOGGING
# ==========================================

logger = logging.getLogger(__name__)


# ==========================================
# 2. DATABASE INITIALIZATION
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# ==========================================
# 3. FASTAPI APPLICATION
# ==========================================

app = FastAPI(
    title="Shipping Analytics Agent",
    version="0.3.1",
    lifespan=lifespan,
)


class MessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=1000)


# ==========================================
# 4. HEALTH CHECK
# ==========================================

@app.get("/healthz")
def health_check():
    return {"status": "ok"}


# ==========================================
# 5. LIST USER CONVERSATIONS
# ==========================================

@app.get("/api/v1/conversations")
def get_conversations(
    user_id: str = Depends(get_current_user),
):
    return {
        "conversations": list_conversations(user_id)
    }


# ==========================================
# 6. CREATE CONVERSATION
# ==========================================

@app.post("/api/v1/conversations", status_code=201)
def new_conversation(
    user_id: str = Depends(get_current_user),
):
    return create_conversation(user_id)


# ==========================================
# 7. READ CONVERSATION
# ==========================================

@app.get("/api/v1/conversations/{conversation_id}")
def read_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user),
):
    conversation = get_conversation(
        conversation_id,
        user_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    return conversation


# ==========================================
# 8. SEND MESSAGE TO AI AGENT
# ==========================================

@app.post(
    "/api/v1/conversations/{conversation_id}/messages"
)
def send_message(
    conversation_id: str,
    payload: MessageRequest,
    user_id: str = Depends(get_current_user),
):

    # STEP 1: Verifikasi kepemilikan conversation
    conversation = get_conversation(
        conversation_id,
        user_id,
    )

    if conversation is None:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    # STEP 2: Ambil maksimal 6 pesan terakhir
    # Perbaikan: menggunakan key "messages"
    history = conversation["messages"][-6:]

    logger.info("Checkpoint 1: Conversation history loaded")

    # STEP 3: Jalankan AI Agent
    try:
        result = run_agent(
            payload.content,
            history=history,
        )

        logger.info("Checkpoint 2: AI Agent completed")

        # Validasi struktur hasil AI Agent
        required_keys = {
            "answer",
            "data_basis",
            "outcome",
        }

        if not isinstance(result, dict) or not required_keys.issubset(result):
            raise ValueError("Incomplete agent response")

        logger.info("Checkpoint 3: Agent response validated")

    except Exception as exc:
        # Hindari mencetak error mentah yang mungkin
        # mengandung data atau konfigurasi sensitif
        logger.error(
            "Agent failed: %s",
            type(exc).__name__,
        )

        return JSONResponse(
            status_code=503,
            content={
                "detail": "Analytics service unavailable"
            },
        )

    # STEP 4: Simpan pertanyaan dan jawaban ke SQLite
    try:
        saved = save_exchange(
            conversation_id,
            user_id,
            payload.content,
            result["answer"],
        )

    except Exception as exc:
        logger.error(
            "Conversation save failed: %s",
            type(exc).__name__,
        )

        return JSONResponse(
            status_code=503,
            content={
                "detail": "Conversation service unavailable"
            },
        )

    if not saved:
        raise HTTPException(
            status_code=404,
            detail="Conversation not found",
        )

    logger.info("Checkpoint 4: Conversation saved")

    # STEP 5: Return response ke UI
    return {
        "conversation_id": conversation_id,
        "answer": result["answer"],
        "data_basis": result["data_basis"],
        "outcome": result["outcome"],
    }
