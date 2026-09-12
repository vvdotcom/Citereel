FROM node:22-bookworm AS web
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY src ./src
COPY public ./public
COPY assets ./assets
COPY tsconfig.json next.config.ts next-env.d.ts ./
RUN npm run build

FROM node:22-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y python3 python3-venv ffmpeg && rm -rf /var/lib/apt/lists/*
COPY requirements.txt ./
RUN python3 -m venv .venv && .venv/bin/pip install --no-cache-dir -r requirements.txt && .venv/bin/python -m playwright install --with-deps chromium
COPY --from=web /app/node_modules ./node_modules
COPY --from=web /app/.next ./.next
COPY --from=web /app/public ./public
COPY package.json next.config.ts ./
COPY services ./services
COPY scripts ./scripts
COPY assets ./assets
ENV LAUNCHPAD_WEB_HOST=0.0.0.0 LAUNCHPAD_WEB_PORT=3011 LAUNCHPAD_LOCAL_MODE=false LAUNCHPAD_VOICE=polly LAUNCHPAD_DATA_DIR=/data
VOLUME /data
EXPOSE 3011
CMD ["node","scripts/dev.mjs","--production"]
