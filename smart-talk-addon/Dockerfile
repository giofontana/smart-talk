ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base-python:3.12
FROM ${BUILD_FROM}

# Install system dependencies
RUN apk add --no-cache \
    supervisor \
    ffmpeg \
    espeak-ng \
    build-base \
    libffi-dev \
    && rm -rf /var/cache/apk/*

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
