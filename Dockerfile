# Edge Crew v3.0 - Railway Deploy
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

# Railway sets PORT env var, default to 8000
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
