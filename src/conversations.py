
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_connection():
    configured_path = Path(
        os.getenv(
            "SQLITE_PATH",
            "./data/conversations.sqlite3"
        )
    )

    db_path = (
        configured_path
        if configured_path.is_absolute()
        else BASE_DIR / configured_path
    )

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL
                    CHECK (role IN ('user', 'assistant')),
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id)
                    REFERENCES conversations(id)
            );

            CREATE INDEX IF NOT EXISTS idx_owner
            ON conversations(user_id);

            CREATE INDEX IF NOT EXISTS idx_messages
            ON messages(conversation_id, created_at);
        """)


def create_conversation(user_id):
    conversation_id = str(uuid.uuid4())
    now = utc_now()

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO conversations
                (id, user_id, title, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (conversation_id, user_id,
             "New conversation", now),
        )

    return {
        "id": conversation_id,
        "title": "New conversation",
        "updated_at": now,
    }


def list_conversations(user_id):
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, title, updated_at
            FROM conversations
            WHERE user_id = ?
            ORDER BY updated_at DESC
            """,
            (user_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_conversation(conversation_id, user_id):
    with get_connection() as conn:
        owner = conn.execute(
            """
            SELECT id
            FROM conversations
            WHERE id = ? AND user_id = ?
            """,
            (conversation_id, user_id),
        ).fetchone()

        if owner is None:
            return None

        rows = conn.execute(
            """
            SELECT role, content, created_at
            FROM messages
            WHERE conversation_id = ?
            ORDER BY created_at, rowid
            """,
            (conversation_id,),
        ).fetchall()

    return {
        "id": conversation_id,
        "messages": [dict(row) for row in rows],
    }


def save_exchange(
    conversation_id,
    user_id,
    question,
    answer,
):
    now = utc_now()

    with get_connection() as conn:
        # Pemeriksaan ownership dan penyimpanan
        # berlangsung dalam satu transaksi
        conn.execute("BEGIN IMMEDIATE")

        owner = conn.execute(
            """
            SELECT id, title
            FROM conversations
            WHERE id = ? AND user_id = ?
            """,
            (conversation_id, user_id),
        ).fetchone()

        if owner is None:
            return False

        for role, content in (
            ("user", question),
            ("assistant", answer),
        ):
            conn.execute(
                """
                INSERT INTO messages
                    (id, conversation_id, role,
                     content, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    conversation_id,
                    role,
                    content,
                    now,
                ),
            )

        title = owner["title"]
        if title == "New conversation":
            title = question[:60]

        conn.execute(
            """
            UPDATE conversations
            SET title = ?, updated_at = ?
            WHERE id = ? AND user_id = ?
            """,
            (title, now, conversation_id, user_id),
        )

    return True
