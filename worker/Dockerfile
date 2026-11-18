# Overthought Studio worker — build from repo root:  docker build -f worker/Dockerfile .
FROM public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    STUDIO_ASSETS=/app/assets STUDIO_WORK=/data/work

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY worker/requirements.txt worker/requirements.txt
RUN pip install --no-cache-dir -r worker/requirements.txt

COPY assets/style/fonts assets/style/fonts
COPY worker/studio worker/studio

RUN useradd -m -u 10001 studio && mkdir -p /data/work && chown -R studio /data
USER studio
WORKDIR /app/worker
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "studio.main"]
