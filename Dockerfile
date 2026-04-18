# Use official PyTorch CUDA runtime image
FROM pytorch/pytorch:2.2.0-cuda12.1-cudnn8-runtime

# Set the working directory
WORKDIR /app

# Prevent Python from writing .pyc files & buffer output
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies (required for some Python packages like lxml, regex, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential gcc g++ && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies and runtime required tools (like fastapi & uvicorn)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir fastapi uvicorn python-multipart python-docx pdfplumber pypdf pytesseract Pillow

# Copy the rest of the application
COPY . .

# Expose port
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "app.server:app", "--host", "0.0.0.0", "--port", "8080"]
