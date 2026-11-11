# -*- coding: utf-8 -*-
"""
Configuration for Book Organizer
"""
import os
import re
import datetime

DEFAULT_SRC_DIR = r"G:\123"
DEFAULT_DST_DIR = r"D:\downloads\魏总的书库（已整理）(1)"

HTTP_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Referer": "https://book.douban.com/"
}

REQUEST_DELAY = 1.2
REQUEST_TIMEOUT = 12

SUPPORTED_EXTENSIONS = ('.epub', '.mobi', '.azw3', '.pdf', '.txt')

COLLECTION_KEYWORDS = [
    '合集', '大合集', '必读合集', '精选合集', '严选', '选集',
    '全集', '大全集', '文集', '作品集', '丛书', '书系', '系列',
    '套装', '全本', '校对版', '合订本', '精选集', '大合订',
    '文选', '汇编'
]

COLLECTION_REGEXES = [
    re.compile(r'(?:全|共|套装共?)\s*\d+\s*(?:册|卷|本|部)'),
    re.compile(r'\d+\s*部曲'),
    re.compile(r'\+'),
]

INVALID_CHARS = [':', '：', '/', '\\', '*', '?', '"', '<', '>', '|']

def sanitize_filename(name: str) -> str:
    if not name:
        return ""
    for ch in INVALID_CHARS:
        name = name.replace(ch, '')
    name = re.sub(r'\s+', ' ', name).strip(' .')
    return name

def format_iso_datetime(date_str: str) -> str:
    if not date_str:
        return datetime.datetime.now(datetime.timezone.utc).isoformat()
    date_str = str(date_str).strip()
    if 'T' in date_str and ('+' in date_str or 'Z' in date_str):
        return date_str
    m = re.search(r'(\d{4})(?:[-/.](\d{1,2}))?(?:[-/.](\d{1,2}))?', date_str)
    if m:
        year = int(m.group(1))
        month = int(m.group(2)) if m.group(2) else 1
        day = int(m.group(3)) if m.group(3) else 1
        try:
            return datetime.datetime(year, month, day, 0, 0, 0, tzinfo=datetime.timezone.utc).isoformat()
        except Exception:
            pass
    return datetime.datetime.now(datetime.timezone.utc).isoformat()
