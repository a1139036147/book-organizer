# =============================================================
# Stage 1: Build Koodo Reader web app from source
# =============================================================
FROM node:18-slim AS koodo-builder

RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates && rm -rf /var/lib/apt/lists/*

WORKDIR /koodo
RUN git clone --depth 1 https://github.com/koodo-reader/koodo-reader.git . \
    && npm ci --legacy-peer-deps \
    && npm run build \
    && rm -rf node_modules .git

# =============================================================
# Stage 2: Main application
# =============================================================
FROM python:3.12-slim

WORKDIR /app

ARG APP_VERSION=2.6.0
ARG BUILD_DATE="
ARG GIT_COMMIT="

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PORT=14808 \
    APP_VERSION= \
    BUILD_DATE= \
    GIT_COMMIT= \
    PGHOST=127.0.0.1 \
    PGPORT=5432 \
    PGUSER=bookuser \
    PGPASSWORD=bookpass123 \
    PGDATABASE=book_library

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    libxml2 \
    libxslt1.1 \
    tzdata \
    ca-certificates \
    curl \
    procps \
    git \
    postgresql \
    postgresql-contrib \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

# Copy Koodo Reader pre-built static site from Stage 1
COPY --from=koodo-builder /koodo/build /app/koodo_reader

RUN chmod +x /app/entrypoint.sh

VOLUME [ /source, /library, /config]
EXPOSE 14808

ENTRYPOINT [/app/entrypoint.sh]
CMD [web]
