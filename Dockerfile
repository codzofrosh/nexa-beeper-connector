FROM python:3.12-slim

# System deps
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Working directory
WORKDIR /app

# Copy requirements first (better caching)
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the code
COPY . .

# Environment
ENV PYTHONUNBUFFERED=1
ENV ENABLE_EXECUTOR=0

# Expose API
EXPOSE 8080

# Start server
CMD ["uvicorn", "sidecar.main:app", "--host", "0.0.0.0", "--port", "8080"]
