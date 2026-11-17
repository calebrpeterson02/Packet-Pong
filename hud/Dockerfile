FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    # No sound in the HUD; stops SDL from complaining about missing ALSA devices
    SDL_AUDIODRIVER=dummy
WORKDIR /app

# The pygame wheel bundles SDL2, but SDL loads the X11 client libraries from the system
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libx11-6 libxext6 libxrender1 libxcursor1 libxi6 libxrandr2 libxfixes3 libxss1 \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY hud.py .

# PLAYER (A or B) is supplied at runtime (env_file / -e), not baked into the image
CMD ["python", "hud.py"]
