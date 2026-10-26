FROM python:3.12-slim

WORKDIR /app

COPY apps/ui ./apps/ui

RUN pip install --no-cache-dir "streamlit>=1.40.0" "httpx>=0.27.0"

ENV API_BASE_URL=http://api:8000

EXPOSE 8501

WORKDIR /app/apps/ui
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0", "--server.port", "8501"]
