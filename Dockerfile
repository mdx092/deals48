# ================================
#   Python Base Image
# ================================
FROM python:3.11-slim

# Prevent Python from buffering output
ENV PYTHONUNBUFFERED=1

# Create app dir
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files
COPY . .

# Render provides PORT — expose it
EXPOSE 10000

# Start the bot + Flask webhook server
CMD ["python", "main.py"]
