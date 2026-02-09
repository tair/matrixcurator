# syntax=docker/dockerfile:1
FROM python:3.12

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app

# ---- system tools ----
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential gcc libffi-dev libssl-dev libreoffice ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# ---- Python deps ----
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- FastAPI code ----
COPY app.py ./
COPY src ./src

# ---- expose & run API ----
EXPOSE 8001
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]