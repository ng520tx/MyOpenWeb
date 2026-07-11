# ─── Stage 1: build the H5 frontend ────────────────────────
FROM node:18-alpine AS web
WORKDIR /app

RUN npm install -g pnpm@10

COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY index.html vite.config.ts tsconfig.json tsconfig.node.json tailwind.config.js postcss.config.js ./
COPY src ./src
RUN pnpm build

# ─── Stage 2: FastAPI runtime serving API + built H5 ───────
FROM python:3.12-slim
WORKDIR /app

COPY server/requirements.txt server/requirements-pgvector.txt ./server/
# pgvector driver ships in the image so switching backends is env-only.
RUN pip install --no-cache-dir -r server/requirements.txt -r server/requirements-pgvector.txt

COPY server ./server
COPY --from=web /app/dist ./dist

# All persisted state (SQLite + uploaded files) lives under /data (volume).
ENV MYOPENWEB_DATA_DIR=/data
VOLUME /data

EXPOSE 8000
CMD ["uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]
