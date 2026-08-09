FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_TRUSTED_HOST="pypi.org files.pythonhosted.org pypi.python.org"

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port
EXPOSE 8080

# Start the FastAPI app with uvicorn
CMD ["uvicorn", "run_gateway:app", "--host", "0.0.0.0", "--port", "8080"]