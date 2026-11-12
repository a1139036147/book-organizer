# -------------------------------------------------------------
# Dockerfile for Book Organizer All-in-One (内置 PostgreSQL + 原版 Koodo Reader)
# -------------------------------------------------------------
FROM ghcr.io/koodo-reader/koodo-reader:latest AS koodo-asset

FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PORT=14808 \
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
    postgresql \
    postgresql-contrib \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 将原装正版官方 Koodo Reader 纯静态应用完整塞入
COPY --from=koodo-asset /usr/share/caddy /app/koodo_reader

COPY config.py .
COPY metadata_provider.py .
COPY epub_handler.py .
COPY opf_generator.py .
COPY book_organizer.py .
COPY bookshelf_manager.py .
COPY calibre_shim.py .
COPY db_manager.py .
COPY web_app.py .
COPY entrypoint.sh .

RUN chmod +x entrypoint.sh

VOLUME ["/source", "/library", "/config"]
EXPOSE 14808

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
