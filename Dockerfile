# -------------------------------------------------------------
# Dockerfile for Book Organizer & Bookshelf (智能图书整理与书架管理系统)
# -------------------------------------------------------------
FROM python:3.12-slim

# 设置工作目录与系统环境变量
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8 \
    PORT=14808

# 安装系统运行依赖与中文字体支持 (确保在 Linux/Docker 中封面文字与元数据正常渲染)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-wqy-microhei \
    fonts-wqy-zenhei \
    libxml2 \
    libxslt1.1 \
    tzdata \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# 复制 Python 依赖清单并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制核心源码文件
COPY config.py .
COPY metadata_provider.py .
COPY epub_handler.py .
COPY opf_generator.py .
COPY book_organizer.py .
COPY bookshelf_manager.py .
COPY calibre_shim.py .
COPY web_app.py .
COPY entrypoint.sh .

# 赋予入口脚本可执行权限
RUN chmod +x entrypoint.sh

# 声明标准数据卷挂载点:
# /source : 宿主机待整理电子书源目录
# /library: 宿主机已整理规范化书库目录
# /config : 配置文件 settings.json 持久化目录
VOLUME ["/source", "/library", "/config"]

# 暴露 Web 访问端口
EXPOSE 14808

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["web"]
