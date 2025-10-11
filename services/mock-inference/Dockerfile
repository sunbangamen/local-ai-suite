FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install curl for container healthchecks
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY app.py .

ENV PORT=8001
ENV MODEL_NAME=mock-model

EXPOSE 8001

CMD ["python", "app.py"]
