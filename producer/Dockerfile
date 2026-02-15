FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY producer.py .

# config/ is mounted at /config at runtime via docker-compose volume
CMD ["python", "-u", "producer.py"]
