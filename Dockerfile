# Multi-stage Dockerfile for CLAW PromptOps Backend and Streamlit UI

FROM python:3.11-slim as base

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install base system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application directories and files
COPY app/ app/
COPY prompts/ prompts/
COPY schemas/ schemas/
COPY evaluation/ evaluation/
COPY ui/ ui/
COPY docs/ docs/
COPY .env.example .env

# Expose ports: 8000 (FastAPI API), 8501 (Streamlit Dashboard)
EXPOSE 8000
EXPOSE 8501

# Default launch command: starts the FastAPI API server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
