FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirement.txt ./

# Install dependencies
RUN pip install --no-cache-dir -r requirement.txt

# Copy project files
COPY . .

# Expose port
EXPOSE 8000

# Start the FastAPI app with uvicorn
CMD ["uvicorn", "run_gateway:app", "--host", "0.0.0.0", "--port", "8000"]