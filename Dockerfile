FROM python:3.11-slim

# Install system dependencies including espeak-ng and ffmpeg (needed for audio conversion)
RUN apt-get update && apt-get install -y \
    espeak-ng \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server code
COPY server.py .

# Expose the port the server runs on
EXPOSE 8013

# Run the server
CMD ["python", "server.py"]