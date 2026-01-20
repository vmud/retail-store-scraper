# Multi-Retailer Store Scraper Docker Image
# Multi-stage build for security and smaller image size (#64)

# Build stage - install dependencies
FROM python:3.11-slim AS builder

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install system dependencies needed for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip to suppress update notices, then install dependencies
# Use --no-warn-script-location to suppress PATH warnings during build
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --no-warn-script-location --user -r requirements.txt


# Runtime stage - minimal image
FROM python:3.11-slim

# Prevent interactive prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Create non-root user for security (#64)
RUN useradd -m -u 1000 -s /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/appuser/.local

# Copy application code
COPY --chown=appuser:appuser . .

# Copy and set up entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Create all data directories with subdirectories before USER switch
RUN mkdir -p /app/data/{att,verizon,target,tmobile,walmart,bestbuy}/{output,checkpoints,runs,history} \
    /app/logs \
    /app/dashboard && \
    touch /app/.flask_secret && \
    chown -R appuser:appuser /app/data /app/logs /app/.flask_secret

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

# Set entrypoint to handle permissions and directory setup
ENTRYPOINT ["/docker-entrypoint.sh"]

# Default command - start the dashboard (aligns with healthcheck)
# Override with: docker run <image> python run.py --all --resume
CMD ["python", "dashboard/app.py"]
