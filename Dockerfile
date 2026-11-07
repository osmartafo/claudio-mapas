FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libfontconfig1 libgl1 libegl1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# Chromium sin ventana para dibujar las escenas 3D (three.js)
RUN python -m playwright install --with-deps chromium && rm -rf /var/lib/apt/lists/*
COPY . .
ENV FRONTERAS_SALIDA=/app/videos PYTHONUNBUFFERED=1
CMD ["python", "-m", "fronteras.bot"]
