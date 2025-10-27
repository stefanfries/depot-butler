# Use official Python runtime as base image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy dependency files and source code
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies using uv
RUN uv pip install --system --no-cache -e .

# Create directory for persistent data (will be mounted in Azure)
RUN mkdir -p /mnt/data

# Run the application
CMD ["python", "-m", "depotbutler"]
