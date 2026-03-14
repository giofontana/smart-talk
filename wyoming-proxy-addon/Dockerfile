FROM python:3.12-slim

# Install dependencies
COPY requirements.txt /tmp/
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy application code
WORKDIR /app
COPY src/ /app/src/
COPY run.sh /app/

# Make run script executable
RUN chmod +x /app/run.sh

# Run the proxy
CMD ["/app/run.sh"]
