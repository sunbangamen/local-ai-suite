FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy memory system from scripts
COPY ../../scripts/memory_system.py /app/scripts/
COPY ../../scripts/memory_utils.py /app/scripts/

# Copy service code
COPY app.py .

# Expose port
EXPOSE 8005

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8005/health')"

# Run service
CMD ["python", "app.py"]