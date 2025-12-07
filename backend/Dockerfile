# backend/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# system deps required by some python libs (psycopg2, PyMuPDF, tokenizers, spacy)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    curl \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# copy requirements first for Docker layer caching
COPY requirements.txt /app/requirements.txt

# install wheel first, then requirements
RUN pip install --upgrade pip wheel setuptools
RUN pip install --no-cache-dir -r /app/requirements.txt

# copy project files
COPY . /app

# ensure entrypoint/script is executable (if used)
RUN chmod +x /app/wait_for_postgres.sh || true

# dev: expose port 8000
EXPOSE 8000

# default command overridden by docker-compose service command
CMD ["sh", "-c", "python manage.py runserver 0.0.0.0:8000"]
