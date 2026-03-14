FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY deployment/demo-app/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy source modules and demo app
COPY src/ /app/src/
COPY deployment/demo-app/main.py /app/main.py

# Create data directory for API logs (Rule R-3)
RUN mkdir -p /app/data/api_logs

# The src/ imports use PROJECT_ROOT which resolves to /app
# Set PYTHONPATH so src/ is importable
ENV PYTHONPATH=/app

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
