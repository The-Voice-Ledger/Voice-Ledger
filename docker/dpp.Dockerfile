# Voice Ledger - DPP Resolver Service
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
COPY twin/ ./twin/
COPY dpp/ ./dpp/

# Create directories for data persistence
RUN mkdir -p /app/twin /app/dpp/passports /app/dpp/qrcodes

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/')"

# Run the DPP resolver service
CMD ["python", "-m", "uvicorn", "dpp.dpp_resolver:app", "--host", "0.0.0.0", "--port", "8001"]
