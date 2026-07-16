FROM python:3.12-slim

# Docker CLI (for spawning sibling compression containers via the host socket)
COPY --from=docker:cli /usr/local/bin/docker /usr/local/bin/docker

RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .
