FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

ENV PORT=8001
ENV MODEL_NAME=mock-model

EXPOSE 8001

CMD ["python", "app.py"]
