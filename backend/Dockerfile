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

# Huggingface authetication
ARG HF_TOKEN
ENV HUGGINGFACE_HUB_TOKEN=$HF_TOKEN
# Disable HF telemetry and online downloads (TRANSFORMERS_OFFLINE=0 allow download during build)
ENV TRANSFORMERS_OFFLINE=0
ENV HF_HUB_DISABLE_TELEMETRY=1

# Preload SentenceTransformer model
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application code
COPY . .

# Make cache accessible to appuser
RUN mkdir -p /root/.cache /home/appuser/.cache \
 && chmod -R 777 /root/.cache /home/appuser/.cache
ENV TRANSFORMERS_CACHE=/root/.cache/huggingface

# Create non-root user --> Avoids priviledge escalation vulnerabilities
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app
USER appuser

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
ENV FLASK_ENV=production

# Expose port for Cloud Run
EXPOSE 8080

# Start the app
CMD ["gunicorn", "--bind", ":8080", "app.main:create_app()"]