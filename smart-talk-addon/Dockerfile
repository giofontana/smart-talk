FROM python:3.12-slim-bookworm

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    supervisor \
    ffmpeg \
    espeak-ng \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy application code
COPY app/ /app/
COPY supervisord.conf /etc/supervisord.conf

# Create directories for model storage and runtime data
RUN mkdir -p /share/smart_talk/piper_models \
    && mkdir -p /share/smart_talk/whisper_models \
    && mkdir -p /data

WORKDIR /app

ENTRYPOINT ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
