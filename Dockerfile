# -------------------------------------------------------------
# Dockerfile for Book Organizer All-in-One (内置 PostgreSQL + 规范化书库与阅读器)
# -------------------------------------------------------------
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

# 安装系统运行依赖、中文字体、curl 以及内置 PostgreSQL
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

# 复制全部应用源码与静态资源
COPY . /app/

RUN chmod +x /app/entrypoint.sh

VOLUME ["/source", "/library", "/config"]
EXPOSE 14808

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
