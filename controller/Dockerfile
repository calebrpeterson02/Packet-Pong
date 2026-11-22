FROM python:3.11-slim-bookworm

# Print logs immediately instead of buffering them
ENV PYTHONUNBUFFERED=1
WORKDIR /app

# sense-hat depends on RTIMULib, which compiles from source, so it needs a C++ toolchain
COPY requirements.txt .
RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential \
 && pip install --no-cache-dir -r requirements.txt \
 && rm -rf /var/lib/apt/lists/*

COPY controller.py .

# PLAYER and ENGINE_IP are supplied at runtime (env_file / -e), not baked into the image
CMD ["python", "controller.py"]
