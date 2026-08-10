# Tells the docker file what package to use
FROM python:3.14.0-slim

# Tells docker what directory to use (internal to container)
WORKDIR /app

# Copy and install requirements
COPY ./docker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and data
COPY src/ ./src/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Run the application
CMD ["python3", "src/spotibot.py"]
