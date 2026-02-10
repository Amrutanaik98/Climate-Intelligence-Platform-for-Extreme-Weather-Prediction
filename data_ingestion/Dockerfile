# Base image — slim means minimal OS (smaller = faster)
FROM python:3.11-slim

# Set working directory inside the container
WORKDIR /app

# Install system dependencies (needed for confluent-kafka)
RUN apt-get update && apt-get install -y \
    build-essential \
    librdkafka-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (Docker caches this layer)
# If requirements.txt hasn't changed, Docker skips reinstalling packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all source code
COPY . .

# Environment variables (can be overridden in docker-compose.yml)
ENV PYTHONUNBUFFERED=1
ENV KAFKA_BOOTSTRAP_SERVERS=kafka-1:9092
ENV SCHEMA_REGISTRY_URL=http://schema-registry:8081
ENV FETCH_INTERVAL_SECONDS=30

# Health check — Docker restarts container if this fails
HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8081/subjects')" || exit 1

# Run the producer
CMD ["python", "kafka_producer_openweather.py"]