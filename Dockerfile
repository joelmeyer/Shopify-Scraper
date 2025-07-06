# Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt && pip install supervisor

COPY . .

# Create logs directory for logging
RUN mkdir -p logs
RUN mkdir -p data

COPY supervisord.conf /etc/supervisord.conf

ENV FLASK_APP=webapp/web_ui.py
ENV FLASK_RUN_HOST=0.0.0.0

EXPOSE 5000

CMD ["supervisord", "-c", "/etc/supervisord.conf"]
