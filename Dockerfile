FROM python:3.11-slim-bookworm

WORKDIR /app

# System deps needed for audio and for installing Python packages that may compile
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libsndfile1 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Upgrade pip first (helps with pre-release / metadata edge cases)
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENV PORT=8000
EXPOSE 8000

CMD ["bash", "-lc", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
