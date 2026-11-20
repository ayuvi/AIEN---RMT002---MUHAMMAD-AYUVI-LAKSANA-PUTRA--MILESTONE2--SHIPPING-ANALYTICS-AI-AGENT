import os
import secrets

from dotenv import load_dotenv
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

load_dotenv()

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        bearer_scheme
    ),
) -> str:
    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_a = os.getenv("DEMO_TOKEN_A")
    token_b = os.getenv("DEMO_TOKEN_B")

    if not token_a or not token_b or token_a == token_b:
        raise HTTPException(
            status_code=503,
            detail="Authentication service unavailable",
        )

    token = credentials.credentials

    if secrets.compare_digest(token, token_a):
        return "user_a"

    if secrets.compare_digest(token, token_b):
        return "user_b"

    raise HTTPException(
        status_code=401,
        detail="Invalid or missing token",
        headers={"WWW-Authenticate": "Bearer"},
    )
