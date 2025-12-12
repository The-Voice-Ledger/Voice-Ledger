# Voice Ledger - Voice API Service
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY gs1/ ./gs1/
COPY epcis/ ./epcis/
COPY voice/ ./voice/
COPY ssi/ ./ssi/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/')"

# Run the voice API service
CMD ["python", "-m", "uvicorn", "voice.service.api:app", "--host", "0.0.0.0", "--port", "8000"]
