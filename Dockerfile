FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# Dependencies untuk FastAPI, Streamlit,
# OpenAI, Neon PostgreSQL, dan SQL Guard.
RUN pip install --no-cache-dir \
    fastapi \
    "uvicorn[standard]" \
    streamlit \
    openai \
    python-dotenv \
    "psycopg[binary]" \
    sqlglot \
    requests \
    httpx


COPY src/ ./src/
COPY app.py ./app.py

# Folder SQLite persistent volume.
RUN mkdir -p /app/data

EXPOSE 8000 8501

CMD ["uvicorn", "src.api:app", "--host", "0.0.0.0", "--port", "8000"]
