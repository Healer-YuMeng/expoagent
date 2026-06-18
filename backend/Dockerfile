FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    libgomp1 \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/backend/requirements.txt

RUN pip install --upgrade pip && \
    pip install -r /app/backend/requirements.txt

COPY backend /app/backend

RUN mkdir -p /app/backend/logs \
    /app/backend/rag/data/knowledge_base \
    /app/backend/rag/data/chroma/vector_store \
    /app/backend/rag/data/rag/chroma \
    /app/backend/rag/data/tmp_uploads \
    /app/backend/app/static

EXPOSE 9008

CMD ["sh", "-c", "uvicorn app.main:app --host ${BACKEND_HOST:-0.0.0.0} --port ${BACKEND_PORT:-9008}"]
