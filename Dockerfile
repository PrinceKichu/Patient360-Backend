# Use official Python runtime as base image
FROM python:3.11.5-slim
 
# Set working directory in container
WORKDIR /app
 
# Copy requirements file first (for better caching)
COPY requirements.txt ./
 
# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt
 
# Copy the rest of the application code
COPY . .
 
# Expose port 8001 (default for FastAPI/Uvicorn)
EXPOSE 8002
 
# Command to run the FastAPI application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]