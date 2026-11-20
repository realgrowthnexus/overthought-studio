# Overthought Studio worker — build from repo root:  docker build -f worker/Dockerfile .
# Node 22 for Claude Code (Debian's nodejs package is too old for it)
FROM public.ecr.aws/docker/library/node:22-slim AS node

FROM public.ecr.aws/docker/library/python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DISABLE_AUTOUPDATER=1 \
    STUDIO_ASSETS=/app/assets STUDIO_WORK=/data/work

RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg ca-certificates tini \
 && rm -rf /var/lib/apt/lists/*

# Claude Code (headless) — the worker's Claude calls run through it, signed in with the owner's Claude plan.
# Pinned: a new CLI version can change its output format; bump deliberately and re-run the tests.
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && npm install -g --no-fund --no-audit @anthropic-ai/claude-code@2.1.329 \
 && npm cache clean --force && claude --version

WORKDIR /app
COPY worker/requirements.txt worker/requirements.txt
RUN pip install --no-cache-dir -r worker/requirements.txt

COPY assets/style/fonts assets/style/fonts
COPY worker/studio worker/studio

# Files must be readable by the non-root user even if the checkout was made with a strict umask (077).
RUN chmod -R a+rX /app \
 && useradd -m -u 10001 studio && mkdir -p /data/work && chown -R studio /data
USER studio
WORKDIR /app/worker
ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "-m", "studio.main"]
