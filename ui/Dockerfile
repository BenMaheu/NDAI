FROM python:3.11-slim

WORKDIR /app

# Copy poetry files first (for caching)
COPY pyproject.toml ./
RUN pip install poetry && poetry install --no-interaction --no-ansi

# Create non-root user --> Avoids priviledge escalation vulnerabilities
RUN adduser --disabled-password --gecos '' appuser && chown -R appuser /app

# Copy app code
COPY . .

EXPOSE 8080
CMD ["poetry", "run", "streamlit", "run", "streamlit_app.py", "--server.port=8080", "--server.address=0.0.0.0"]