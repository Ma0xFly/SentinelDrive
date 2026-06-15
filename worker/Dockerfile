FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY sentineldrive_worker ./sentineldrive_worker
COPY scripts ./scripts
RUN chmod +x scripts/*.sh

CMD ["./scripts/start-worker.sh"]
