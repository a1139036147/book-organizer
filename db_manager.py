#!/usr/bin/env python
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
            self.pool = pool.ThreadedConnectionPool(
                minconn=1, maxconn=24,
                host=self.host, port=self.port,
                user=self.user, password=self.password,
                database=self.dbname, connect_timeout=5
            )
            self.enabled = True
            if not self.create_tables():
                self.pool.closeall()
                self.enabled = False
                return
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
                    file_mtime_ns BIGINT,
                    source_path VARCHAR(1000),
                    is_collection BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
                ALTER TABLE books ADD COLUMN IF NOT EXISTS file_mtime_ns BIGINT;
                CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn);
                CREATE INDEX IF NOT EXISTS idx_books_file_hash ON books(file_hash);
                CREATE INDEX IF NOT EXISTS idx_books_title_author ON books(title, author);
                """)
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            logger.exception("Unable to initialize the books table")
            return False
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
                cur.execute(
                    "SELECT file_path, file_size, file_mtime_ns, file_hash "
                    "FROM books WHERE file_hash = %s ORDER BY id DESC",
                    (file_hash,),
                )
                for row in cur.fetchall():
                    if self.is_current_file(row):
                        return row
            return None
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
                    tags, cover_path, file_path, file_name, file_size, file_hash, file_mtime_ns,
                    source_path, is_collection, updated_at
                ) VALUES (
                    %(isbn)s, %(title)s, %(author)s, %(publisher)s, %(pub_year)s, %(description)s, %(rating)s,
                    %(tags)s, %(cover_path)s, %(file_path)s, %(file_name)s, %(file_size)s, %(file_hash)s, %(file_mtime_ns)s,
                    %(source_path)s, %(is_collection)s, CURRENT_TIMESTAMP
                )
                ON CONFLICT (file_path) DO UPDATE SET
                    isbn = EXCLUDED.isbn,
                    title = EXCLUDED.title,
                    author = EXCLUDED.author,
                    publisher = EXCLUDED.publisher,
                    pub_year = EXCLUDED.pub_year,
                    description = EXCLUDED.description,
                    rating = COALESCE(EXCLUDED.rating, books.rating),
                    tags = EXCLUDED.tags,
                    cover_path = EXCLUDED.cover_path,
                    file_size = EXCLUDED.file_size,
                    file_hash = EXCLUDED.file_hash,
                    file_mtime_ns = EXCLUDED.file_mtime_ns,
                    source_path = COALESCE(EXCLUDED.source_path, books.source_path),
                    is_collection = EXCLUDED.is_collection,
                    updated_at = CURRENT_TIMESTAMP;
                """, data)
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            logger.exception("Unable to index book in PostgreSQL")
            return False
        finally:
            self.release_conn(conn)

    def is_current_file(self, row):
        path = row.get("file_path")
        if not path:
            return False
        try:
            info = os.stat(path)
        except OSError:
            return False
        if info.st_size != row.get("file_size"):
            return False
        recorded_mtime = row.get("file_mtime_ns")
        if recorded_mtime == info.st_mtime_ns:
            return True
        return self.calculate_file_hash(path) == row.get("file_hash")

    def file_hashes(self):
        conn = self.get_conn()
        if not conn:
            return {}
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT file_path, file_size, file_mtime_ns, file_hash FROM books")
                return {path: (size, mtime, digest) for path, size, mtime, digest in cur.fetchall()}
        finally:
            self.release_conn(conn)

    def record_file(self, path, meta, *, digest=None, source=None, cover=None, is_collection=False,
                    stat=None):
        if not self.enabled:
            return False
        path = os.path.abspath(path)
        stat = stat or os.stat(path)
        digest = digest or self.calculate_file_hash(path)
        if not digest:
            return False
        return self.upsert_book({
            "isbn": (meta.get("isbn") or "").replace("-", "").strip()[:32],
            "title": (meta.get("title") or os.path.basename(path))[:255],
            "author": (meta.get("author") or "")[:255],
            "publisher": (meta.get("publisher") or "")[:255],
            "pub_year": (meta.get("pubdate") or "")[:32],
            "description": meta.get("description") or "",
            "rating": meta.get("rating"),
            "tags": str(meta.get("tags") or ""),
            "cover_path": cover, "file_path": path, "file_name": os.path.basename(path),
            "file_size": stat.st_size, "file_hash": digest, "file_mtime_ns": stat.st_mtime_ns,
            "source_path": source, "is_collection": is_collection,
        })

    def search_books(self, query, page, page_size):
        conn = self.get_conn()
        if not conn:
            raise RuntimeError("Database not connected")
        where = """WHERE strpos(lower(concat_ws(' ', title, author, isbn, publisher,
            description, file_name, file_hash)), lower(%s)) > 0"""
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT count(*) AS total FROM books " + where, (query,))
                total = cur.fetchone()["total"]
                page = max(1, min(page, (total + page_size - 1) // page_size))
                cur.execute(
                    "SELECT * FROM books " + where + " ORDER BY id DESC LIMIT %s OFFSET %s",
                    (query, page_size, (page - 1) * page_size),
                )
                return cur.fetchall(), total, page
        finally:
            self.release_conn(conn)

    def delete_files(self, paths):
        conn = self.get_conn()
        if not conn:
            return
        try:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM books WHERE file_path = ANY(%s)", (paths,))
            conn.commit()
        finally:
            self.release_conn(conn)


db = DatabaseManager()
