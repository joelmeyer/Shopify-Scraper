# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create logs directory for logging
RUN mkdir -p logs
RUN mkdir -p data

CMD ["python", "SScraper.py"]
