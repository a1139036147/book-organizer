# syntax=docker/dockerfile:1
# -------------------------------------------------------------
# Dockerfile for Book Organizer All-in-One (内置 PostgreSQL + Koodo Reader)
# -------------------------------------------------------------
FROM --platform=$BUILDPLATFORM node:22-bookworm-slim AS koodo-web

WORKDIR /koodo-src
ADD --checksum=sha256:d3ceeb1684651d225d1e5904a7a44c49f9d9d138fe6c2159c2c59afb95bc8cae https://codeload.github.com/koodo-reader/koodo-reader/tar.gz/refs/tags/v2.4.7 /tmp/koodo.tar.gz
RUN tar -xzf /tmp/koodo.tar.gz --strip-components=1
COPY koodo-bookshelf.patch /tmp/koodo-bookshelf.patch
RUN apt-get update && apt-get install -y --no-install-recommends patch \
    && rm -rf /var/lib/apt/lists/* \
    && patch -p1 < /tmp/koodo-bookshelf.patch \
    && tar -czf /tmp/koodo-source.tar.gz . \
    && yarn install --frozen-lockfile --ignore-scripts --non-interactive \
    && yarn build \
    && cp LICENSE build/LICENSE \
    && mv /tmp/koodo-source.tar.gz build/koodo-source.tar.gz \
    && test -s build/index.html

FROM python:3.12-slim

WORKDIR /app

ARG APP_VERSION=2.6.0
ARG BUILD_DATE=""
ARG GIT_COMMIT=""

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PORT=14808 \
    APP_VERSION=${APP_VERSION} \
    BUILD_DATE=${BUILD_DATE} \
    GIT_COMMIT=${GIT_COMMIT} \
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

# 复制应用和官方 Koodo Web 构建产物
COPY . /app/
COPY --from=koodo-web /koodo-src/build/ /app/koodo_reader/

RUN chmod +x /app/entrypoint.sh

VOLUME ["/source", "/library", "/config"]
EXPOSE 14808

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
