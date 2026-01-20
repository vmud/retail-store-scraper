# Multi-Retailer Store Scraper Docker Image
# Multi-stage build for security and smaller image size (#64)

# Build stage - install dependencies
FROM python:3.11-slim AS builder

WORKDIR /app

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies to user directory
RUN pip install --no-cache-dir --user -r requirements.txt


# Runtime stage - minimal image
FROM python:3.11-slim

WORKDIR /app

# Create non-root user for security (#64)
RUN useradd -m -u 1000 -s /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Create data and logs directories with correct ownership
RUN mkdir -p /app/data /app/logs && chown -R appuser:appuser /app/data /app/logs

# Install curl for health checks (#115)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Switch to non-root user
USER appuser

# Add user's local bin to PATH
ENV PATH=/home/appuser/.local/bin:$PATH

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV LOG_LEVEL=INFO

# Expose dashboard port
EXPOSE 5001

# Health check for dashboard (#115)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5001/api/status || exit 1

# Default command - start the dashboard (aligns with healthcheck)
# Override with: docker run <image> python run.py --all --resume
CMD ["python", "dashboard/app.py"]
