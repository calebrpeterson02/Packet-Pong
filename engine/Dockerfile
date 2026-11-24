FROM python:3.11-slim-bookworm

# Print logs immediately instead of buffering them
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Build context is the repo root (see docker-compose.yml) so database/ can be copied in
COPY engine/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY database/ database/
COPY engine/game_engine.py .

# DB_* settings are supplied at runtime (env_file), not baked into the image
CMD ["python", "game_engine.py"]
