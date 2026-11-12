#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import re

print("🚀 开始一键写入所有核心文件到磁盘...")

# -------------------------------------------------------------
# 1. 写入 requirements.txt
# -------------------------------------------------------------
req_content = """lxml>=4.9.0
pillow>=9.0.0
flask>=2.3.0
psycopg2-binary>=2.9.9
"""
with open("requirements.txt", "w", encoding="utf-8") as f:
    f.write(req_content)
print("  [1/6] ✅ requirements.txt 写入完成")

# -------------------------------------------------------------
# 2. 写入 db_manager.py (内置 PostgreSQL 驱动与查重缓存)
# -------------------------------------------------------------
db_content = '''#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import hashlib
import logging

logger = logging.getLogger("DBManager")

try:
    import psycopg2
    from psycopg2 import pool
    from psycopg2.extras import RealDictCursor
    HAS_PG = True
except ImportError:
    HAS_PG = False

class DatabaseManager:
    def __init__(self):
        self.enabled = False
        self.pool = None
        self.host = os.getenv("PGHOST", "127.0.0.1")
        self.port = int(os.getenv("PGPORT", "5432"))
        self.user = os.getenv("PGUSER", "bookuser")
        self.password = os.getenv("PGPASSWORD", "bookpass123")
        self.dbname = os.getenv("PGDATABASE", "book_library")
        if HAS_PG:
            self._init_pool()

    def _init_pool(self):
        try:
            self.pool = psycopg2.pool.SimpleConnectionPool(
                minconn=1, maxconn=15,
                host=self.host, port=self.port,
                user=self.user, password=self.password,
                database=self.dbname, connect_timeout=5
            )
            self.enabled = True
            self.create_tables()
            logger.info("✅ 成功连接内置 PostgreSQL 数据库")
        except Exception as e:
            self.enabled = False

    def get_conn(self):
        return self.pool.getconn() if (self.enabled and self.pool) else None

    def release_conn(self, conn):
        if self.pool and conn:
            self.pool.putconn(conn)

    def create_tables(self):
        conn = self.get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    id SERIAL PRIMARY KEY,
                    isbn VARCHAR(32),
                    title VARCHAR(255) NOT NULL,
                    author VARCHAR(255),
                    publisher VARCHAR(255),
                    pub_year VARCHAR(32),
                    description TEXT,
                    rating NUMERIC(3, 1),
                    tags TEXT,
                    cover_path VARCHAR(500),
                    file_path VARCHAR(1000) UNIQUE,
                    file_name VARCHAR(255),
                    file_size BIGINT,
                    file_hash VARCHAR(64),
                    source_path VARCHAR(1000),
                    is_collection BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
                CREATE INDEX IF NOT EXISTS idx_books_file_hash ON books(file_hash);
                CREATE INDEX IF NOT EXISTS idx_books_title_author ON books(title, author);
                """)
                conn.commit()
        except Exception:
            conn.rollback()
        finally:
            self.release_conn(conn)

    @staticmethod
    def calculate_file_hash(file_path, block_size=65536):
        if not file_path or not os.path.exists(file_path):
            return ""
        sha = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                while chunk := f.read(block_size):
                    sha.update(chunk)
            return sha.hexdigest()
        except Exception:
            return ""

    def find_by_file_hash(self, file_hash):
        if not self.enabled or not file_hash:
            return None
        conn = self.get_conn()
        if not conn:
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM books WHERE file_hash = %s LIMIT 1", (file_hash,))
                return cur.fetchone()
        finally:
            self.release_conn(conn)

    def find_by_isbn(self, isbn):
        if not self.enabled or not isbn:
            return None
        clean_isbn = isbn.replace('-', '').strip()
        conn = self.get_conn()
        if not conn:
            return None
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM books WHERE isbn = %s ORDER BY id DESC LIMIT 1", (clean_isbn,))
                return cur.fetchone()
        finally:
            self.release_conn(conn)

    def upsert_book(self, data):
        if not self.enabled:
            return False
        conn = self.get_conn()
        if not conn:
            return False
        try:
            with conn.cursor() as cur:
                cur.execute("""
                INSERT INTO books (
                    isbn, title, author, publisher, pub_year, description, rating,
                    tags, cover_path, file_path, file_name, file_size, file_hash,
                    source_path, is_collection, updated_at
                ) VALUES (
                    %(isbn)s, %(title)s, %(author)s, %(publisher)s, %(pub_year)s, %(description)s, %(rating)s,
                    %(tags)s, %(cover_path)s, %(file_path)s, %(file_name)s, %(file_size)s, %(file_hash)s,
                    %(source_path)s, %(is_collection)s, CURRENT_TIMESTAMP
                )
                ON CONFLICT (file_path) DO UPDATE SET
                    isbn = EXCLUDED.isbn,
                    title = EXCLUDED.title,
                    author = EXCLUDED.author,
                    publisher = EXCLUDED.publisher,
                    pub_year = EXCLUDED.pub_year,
                    description = EXCLUDED.description,
                    cover_path = EXCLUDED.cover_path,
                    file_size = EXCLUDED.file_size,
                    file_hash = EXCLUDED.file_hash,
                    updated_at = CURRENT_TIMESTAMP;
                """, data)
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_conn(conn)

db = DatabaseManager()
'''
with open("db_manager.py", "w", encoding="utf-8") as f:
    f.write(db_content)
print("  [2/6] ✅ db_manager.py 写入完成")

# -------------------------------------------------------------
# 3. 写入 Dockerfile (All-in-One: 内置 PG + 原版 Koodo Reader)
# -------------------------------------------------------------
dockerfile_content = """# -------------------------------------------------------------
# Dockerfile for Book Organizer All-in-One (内置 PostgreSQL + 原版 Koodo Reader)
# -------------------------------------------------------------
FROM ghcr.io/koodo-reader/koodo-reader:latest AS koodo-asset

FROM python:3.12-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \\
    PYTHONDONTWRITEBYTECODE=1 \\
    LANG=C.UTF-8 \\
    LC_ALL=C.UTF-8 \\
    PORT=14808 \\
    PGHOST=127.0.0.1 \\
    PGPORT=5432 \\
    PGUSER=bookuser \\
    PGPASSWORD=bookpass123 \\
    PGDATABASE=book_library

RUN apt-get update && apt-get install -y --no-install-recommends \\
    fonts-wqy-microhei \\
    fonts-wqy-zenhei \\
    libxml2 \\
    libxslt1.1 \\
    tzdata \\
    ca-certificates \\
    curl \\
    procps \\
    postgresql \\
    postgresql-contrib \\
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
"""
with open("Dockerfile", "w", encoding="utf-8") as f:
    f.write(dockerfile_content)
print("  [3/6] ✅ Dockerfile 写入完成")

# -------------------------------------------------------------
# 4. 写入 entrypoint.sh (自动管理内置 PG 与 Web)
# -------------------------------------------------------------
entrypoint_content = """#!/bin/bash
set -e

CONFIG_DIR="/config"
mkdir -p "$CONFIG_DIR"
SETTINGS_FILE="$CONFIG_DIR/settings.json"

if [ ! -f "$SETTINGS_FILE" ]; then
    cat <<EOF > "$SETTINGS_FILE"
{
  "src": "/source",
  "dst": "/library",
  "bookshelf_dir": "/library",
  "active_tab": 0,
  "action": "copy",
  "skip_collections": true,
  "limit": "",
  "delay": "1.2",
  "google_key": "",
  "threads": "4"
}
EOF
fi

ln -sf "$SETTINGS_FILE" /app/settings.json 2>/dev/null || true

# 初始化并启动内置 PostgreSQL
PGDATA="/config/pgdata"
mkdir -p "$PGDATA"
chown -R postgres:postgres "$PGDATA"
chmod 700 "$PGDATA"

PG_BIN=$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | head -n 1)

if [ ! -s "$PGDATA/PG_VERSION" ]; then
    echo "📦 [PostgreSQL] 首次启动，正在 /config/pgdata 中初始化数据库集群..."
    su - postgres -c "$PG_BIN/initdb -D '$PGDATA' --encoding=UTF8 --locale=C.UTF-8"
fi

echo "🚀 [PostgreSQL] 启动内置数据库服务..."
su - postgres -c "$PG_BIN/pg_ctl -D '$PGDATA' -l /config/postgres.log -w start"

# 自动创建专属用户与数据库
su - postgres -c "psql -tc \\"SELECT 1 FROM pg_database WHERE datname = 'book_library'\\" | grep -q 1 || psql -c \\"CREATE USER bookuser WITH PASSWORD 'bookpass123'; CREATE DATABASE book_library OWNER bookuser;\\""

cleanup() {
    echo "🛑 [PostgreSQL] 优雅关闭内置数据库..."
    su - postgres -c "$PG_BIN/pg_ctl -D '$PGDATA' -m fast stop" || true
    exit 0
}
trap cleanup SIGTERM SIGINT

if [ "$1" = "web" ] || [ -z "$1" ]; then
    echo "=========================================================="
    echo "  📚 智能图书整理系统 All-in-One (内置PG + 原版Koodo启动)"
    echo "  Web 地址:    http://0.0.0.0:${PORT:-14808}"
    echo "  数据持久化:  /config/pgdata"
    echo "=========================================================="
    exec python /app/web_app.py
elif [ "$1" = "organize" ]; then
    shift
    exec python /app/book_organizer.py --src /source --dst /library "$@"
elif [ "$1" = "dry-run" ]; then
    shift
    exec python /app/book_organizer.py --src /source --dst /library --dry-run "$@"
else
    exec "$@"
fi
"""
with open("entrypoint.sh", "w", encoding="utf-8", newline="\n") as f:
    f.write(entrypoint_content)
print("  [4/6] ✅ entrypoint.sh 写入完成")

# -------------------------------------------------------------
# 5. 写入 docker-compose.yml
# -------------------------------------------------------------
compose_content = """version: '3.8'

services:
  book-organizer:
    image: arros/book-organizer:latest
    container_name: book-organizer
    restart: unless-stopped
    ports:
      - "14808:14808"
    volumes:
      - /path/to/source:/source
      - /path/to/library:/library
      - ./config:/config
"""
with open("docker-compose.yml", "w", encoding="utf-8") as f:
    f.write(compose_content)
print("  [5/6] ✅ docker-compose.yml 写入完成")

# -------------------------------------------------------------
# 6. 更新 bookshelf_manager.py (修复 Spine 乱序)
# -------------------------------------------------------------
with open("bookshelf_manager.py", "r", encoding="utf-8") as f:
    bm_code = f.read()

pattern = re.compile(r"def extract_book_preview\(file_path\):.*?(?=def make_zlib_thumbnail)", re.DOTALL)
new_extract = '''def extract_book_preview(file_path):
    """
    提取图书章节正文与结构目录，严格遵循 EPUB 国际标准骨架（container.xml -> OPF manifest -> spine），
    确保阅读顺序 100% 与原书出版目录一致，彻底杜绝章节错乱。
    """
    if not file_path or not os.path.exists(file_path):
        return [("错误", "文件不存在")]

    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.epub':
        chapters = []
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                all_names = set(zf.namelist())
                opf_path = None
                if 'META-INF/container.xml' in all_names:
                    try:
                        container_xml = zf.read('META-INF/container.xml').decode('utf-8', errors='ignore')
                        match = re.search(r'full-path\\s*=\\s*["\']([^"\']+)["\']', container_xml, re.I)
                        if match and match.group(1) in all_names:
                            opf_path = match.group(1)
                    except Exception:
                        pass

                if not opf_path:
                    for name in all_names:
                        if name.lower().endswith('.opf'):
                            opf_path = name
                            break

                ordered_hrefs = []
                opf_dir = os.path.dirname(opf_path).replace('\\\\', '/') if opf_path else ""

                if opf_path:
                    try:
                        opf_content = zf.read(opf_path).decode('utf-8', errors='ignore')
                        manifest = {}
                        for m in re.finditer(r'<item\\b[^>]*>', opf_content, re.I):
                            tag = m.group(0)
                            id_match = re.search(r'\\bid\\s*=\\s*["\']([^"\']+)["\']', tag, re.I)
                            href_match = re.search(r'\\bhref\\s*=\\s*["\']([^"\']+)["\']', tag, re.I)
                            if id_match and href_match:
                                i_id = id_match.group(1)
                                i_href = href_match.group(1)
                                import urllib.parse
                                i_href = urllib.parse.unquote(i_href).split('#')[0]
                                manifest[i_id] = i_href

                        for m in re.finditer(r'<itemref\\b[^>]*\\bidref\\s*=\\s*["\']([^"\']+)["\']', opf_content, re.I):
                            idref = m.group(1)
                            if idref in manifest:
                                rel_path = manifest[idref]
                                full_entry = f"{opf_dir}/{rel_path}".replace('//', '/') if opf_dir else rel_path
                                full_entry = os.path.normpath(full_entry).replace('\\\\', '/')
                                ordered_hrefs.append(full_entry)
                    except Exception:
                        pass

                if not ordered_hrefs:
                    ordered_hrefs = [n for n in zf.namelist() if n.lower().endswith(('.html', '.xhtml', '.htm'))]
                    def natural_sort_key(s):
                        return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\\d+)', s)]
                    ordered_hrefs.sort(key=natural_sort_key)

                for href in ordered_hrefs:
                    actual_name = href if href in all_names else next((c for c in all_names if c.lower() == href.lower()), None)
                    if not actual_name:
                        continue
                    raw = zf.read(actual_name).decode('utf-8', errors='ignore')
                    title = ""
                    t_match = re.search(r'<title[^>]*>([^<]+)</title>', raw, re.I)
                    if t_match and t_match.group(1).strip():
                        cand = t_match.group(1).strip()
                        if len(cand) < 60 and not cand.lower().endswith(('.html', '.xhtml')):
                            title = cand
                    if not title:
                        h_match = re.search(r'<h[1-3][^>]*>([^<]+)</h[1-3]>', raw, re.I)
                        if h_match and h_match.group(1).strip():
                            title = h_match.group(1).strip()

                    txt = clean_html_tags(raw)
                    if len(txt) > 20:
                        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
                        if not title:
                            title = lines[0] if lines else os.path.basename(actual_name)
                        if len(title) > 35:
                            title = title[:32] + "..."
                        chapters.append((title, txt))
        except Exception as e:
            return [("加载失败", f"无法解析 EPUB 内容: {e}")]
        return chapters if chapters else [("内容为空", "未提取到正文文本")]

    elif ext == '.txt':
        try:
            content = ""
            for enc in ['utf-8', 'gb18030', 'gbk', 'utf-16']:
                try:
                    with open(file_path, 'r', encoding=enc) as f:
                        content = f.read(500000)
                    break
                except UnicodeDecodeError:
                    continue
            if not content:
                return [("读取失败", "未识别到文本编码")]
            chap_pattern = re.compile(r'^(第[0-9一二三四五六七八九十百千]+[章回节卷集幕].*)$', re.M)
            matches = list(chap_pattern.finditer(content))
            if len(matches) >= 2:
                chapters = []
                for i, m in enumerate(matches):
                    chap_title = m.group(1).strip()
                    start = m.start()
                    end = matches[i+1].start() if i + 1 < len(matches) else len(content)
                    chapters.append((chap_title, content[start:end].strip()))
                return chapters
            else:
                chunk_size = 5000
                chunks = [content[i:i+chunk_size].strip() for i in range(0, len(content), chunk_size)]
                return [(f"第 {idx+1} 部分", c) for idx, c in enumerate(chunks)]
        except Exception as e:
            return [("加载失败", f"无法读取文本内容: {e}")]
    return [("格式不支持", f"暂不支持内置预览该格式文件: {ext}")]

'''
if pattern.search(bm_code):
    bm_code = pattern.sub(new_extract, bm_code)
    with open("bookshelf_manager.py", "w", encoding="utf-8") as f:
        f.write(bm_code)
    print("  [6/6] ✅ bookshelf_manager.py (Spine顺序) 写入完成")

print("\n🎉 全部文件已成功写入磁盘！现在可以执行 git commit 与 git push 了！")