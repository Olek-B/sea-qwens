FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY services/librarian/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY shared/ ./shared/
COPY configs/ ./configs/
COPY services/librarian/ ./services/librarian/

# Set PYTHONPATH so imports resolve from project root
ENV PYTHONPATH=/app

# Set working directory to services/librarian
WORKDIR /app/services/librarian

# Expose the application port
EXPOSE 8001

# Run the application
CMD ["python", "main.py"]
