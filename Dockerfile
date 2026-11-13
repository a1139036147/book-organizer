# -------------------------------------------------------------
# Dockerfile for Book Organizer All-in-One (内置 PostgreSQL + Koodo Reader)
# -------------------------------------------------------------
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

# 复制全部应用源码与预编译好的 Koodo Reader 静态站点
COPY . /app/

# 确保目标目录存在
RUN mkdir -p /app/koodo_reader

RUN chmod +x /app/entrypoint.sh

VOLUME ["/source", "/library", "/config"]
EXPOSE 14808

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]