FROM python:3.11-slim

LABEL maintainer="MarketPulse AI Team"
LABEL description="MarketPulse Coder Worker + Validator"

WORKDIR /app

# Install system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
RUN pip install --no-cache-dir \
    flask \
    pytest \
    mypy \
    ruff

# Copy orchestrator files
COPY . /app/marketpulse-orchestrator/

WORKDIR /app/marketpulse-orchestrator

# Default: run coder_worker
ENTRYPOINT ["python", "workers/coder_worker.py"]
CMD ["--help"]
