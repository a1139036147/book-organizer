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
