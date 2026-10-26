FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY packages/common/src ./packages/common/src
COPY packages/db/src ./packages/db/src
COPY packages/db/alembic ./packages/db/alembic
COPY packages/db/alembic.ini ./packages/db/alembic.ini
COPY packages/rag/src ./packages/rag/src
COPY packages/agent/src ./packages/agent/src
COPY apps/api/src ./apps/api/src
COPY apps/api/entrypoint.sh ./apps/api/entrypoint.sh
COPY data/kb ./data/kb

RUN pip install --no-cache-dir -e ".[dev]" \
    && sed -i 's/\r$//' apps/api/entrypoint.sh \
    && chmod +x apps/api/entrypoint.sh

ENV PYTHONPATH=/app/packages/common/src:/app/packages/db/src:/app/packages/rag/src:/app/packages/agent/src:/app/apps/api/src
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

EXPOSE 8000

CMD ["./apps/api/entrypoint.sh"]
