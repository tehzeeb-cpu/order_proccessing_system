FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared /app/shared
COPY services/notification-service /app/services/notification-service

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app/services/notification-service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8005", "--no-access-log"]
