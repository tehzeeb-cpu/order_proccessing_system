FROM python:3.12-slim

WORKDIR /app

# Copy root requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared library and coordinator source
COPY shared /app/shared
COPY coordinator /app/coordinator
COPY sample_inventory.csv /app/sample_inventory.csv

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app/coordinator
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
