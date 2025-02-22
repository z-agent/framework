FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Only install deps first for caching
COPY requirements.txt .
RUN apt update && \
  apt install -y git && \
  pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "-m", "src.server.main"]
