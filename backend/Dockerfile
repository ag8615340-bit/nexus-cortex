FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (layer caching — rebuild only if requirements change)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Security: remove any .env files from image (secrets must be passed via env vars at runtime)
RUN rm -f .env .env.local .env.production

# Expose backend port
EXPOSE 8000

# Health check — Docker will mark container unhealthy if /health fails
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Run with uvicorn
# Workers=1 for single-instance; increase for production load
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]