# Base image
FROM python:3.11-slim AS builder

# Install system deps for OCR, PDF, build tools
RUN apt-get update && apt-get install -y \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Poetry
RUN curl -sSL https://install.python-poetry.org | python3 -
ENV PATH="/root/.local/bin:$PATH"

# Copy dependency definitions
COPY pyproject.toml poetry.lock* ./

# Configure Poetry
RUN poetry config virtualenvs.create false

# Install Python dependencies
RUN poetry install --no-interaction --no-ansi

# Install torch separately (since it's poetry does not handle it well)
RUN pip install torch --extra-index-url https://download.pytorch.org/whl/cpu
RUN pip install sentence-transformers==5.1.1

# Create non-root user --> Avoids priviledge escalation vulnerabilities
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app

# Huggingface authetication
# TODO: Use BuildKit secrets for better security
ARG HF_TOKEN
ENV HUGGINGFACE_HUB_TOKEN=$HF_TOKEN
ENV HF_HUB_DISABLE_TELEMETRY=1
ENV HF_HUB_DISABLE_PROGRESS_BARS=1
ENV HF_HOME=/app/.cache/huggingface
RUN mkdir -p /app/.cache/huggingface && chmod -R 777 /app/.cache
ENV TRANSFORMERS_OFFLINE=0

# Preload SentenceTransformer model
# TODO: maybe store it in bucket instead
RUN TRANSFORMERS_CACHE=/app/.cache/huggingface python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface

# Copy application code
COPY . .

# Switch to non-root user
USER appuser

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV FLASK_ENV=production
# Set transformers to offline mode
ENV TRANSFORMERS_OFFLINE=1

# Expose port for Cloud Run
EXPOSE 8080

# Start the app
CMD ["gunicorn", "--workers", "2", "--threads", "2", "--bind", ":8080", "app.main:create_app()"]