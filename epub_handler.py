# -*- coding: utf-8 -*-
"""
EPUB File Handler for Book Organizer
Extracts metadata, embedded covers, and cleans book titles/authors
"""
import os
import re
import zipfile
import io
import xml.etree.ElementTree as ET
from PIL import Image

import config

def is_valid_isbn(s):
    if not s:
        return False
    s = s.replace('-', '').replace(' ', '').strip().upper()
    if len(s) == 13 and s.isdigit():
        if not (s.startswith('978') or s.startswith('979')):
            return False
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(s))
        return total % 10 == 0
    elif len(s) == 10:
        if not s[:9].isdigit():
            return False
        check = 10 if s[9] == 'X' else (int(s[9]) if s[9].isdigit() else -1)
        if check == -1:
            return False
        total = sum(int(s[i]) * (10 - i) for i in range(9)) + check
        return total % 11 == 0
    return False

def isbn10_to_isbn13(isbn10):
    isbn10 = isbn10.replace('-', '').replace(' ', '').strip().upper()
    if len(isbn10) == 10 and is_valid_isbn(isbn10):
        core = '978' + isbn10[:9]
        total = sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(core))
        check = (10 - (total % 10)) % 10
        return core + str(check)
    return isbn10

ISBN_REGEX = re.compile(
    r'(?:ISBN(?:-1[03])?[:：\s]*)(97[89][-\s]?(?:\d[-\s]?){9}\d|(?:\d[-\s]?){9}[\dXx])|\b(97[89][-\s]?(?:\d[-\s]?){9}\d)\b',
    re.IGNORECASE
)

def scan_isbns_from_text(text):
    found = set()
    if not text:
        return found
    matches = ISBN_REGEX.findall(text)
    for m1, m2 in matches:
        cand = (m1 or m2).replace('-', '').replace(' ', '').strip().upper()
        if is_valid_isbn(cand):
            found.add(isbn10_to_isbn13(cand))
    return found

def scan_isbns_from_file(file_path):
    """
    直接从图书内部全文检索所有出版ISBN。
    对于EPUB文件：检查OPF元数据、版权页、封面、前言、正文XHTML等。
    返回规范化为13位的有效唯一ISBN集合。
    """
    if not os.path.exists(file_path):
        return set()
    ext = os.path.splitext(file_path)[1].lower()
    found = set()
    if ext == '.epub':
        try:
            with zipfile.ZipFile(file_path, 'r') as z:
                names = z.namelist()
                for name in names:
                    if name.endswith(('.opf', '.html', '.xhtml', '.htm', '.xml', '.ncx')):
                        try:
                            data = z.read(name)
                            text = data.decode('utf-8', errors='ignore')
                            found.update(scan_isbns_from_text(text))
                        except Exception:
                            continue
        except Exception:
            pass
    elif ext == '.txt':
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                head = f.read(300000)
                found.update(scan_isbns_from_text(head))
        except Exception:
            pass
    return found

def clean_author_name(author):
    if not author:
        return ""
    author = author.strip(' :：/\\-')
    ad_kws = [
        '微信', '免费', '公众号', '制作', '整理', '排版', 'www', 'http', '分享', '赠送',
        '扫码', '资源', '精校', '校对', '发布', '独家', '首发', '网', '出品', '下载',
        '群', '关注', '电子书', '小路自制', '多看', '行行', '提供', '搜集'
    ]
    for kw in ad_kws:
        if kw in author:
            return ""
    author = re.sub(r'^(?:作者|著者|编者|著|编)[:：\s]+', '', author)
    author = re.sub(r'\s*(?:著|编|译|整理|校对)$', '', author)
    author = re.sub(r'^(?:[荷美英法德日俄意瑞西班牙加澳韩]|\[[荷美英法德日俄意瑞西班牙加澳韩]\]|[【（][荷美英法德日俄意瑞西班牙加澳韩][】）])\s*', '', author)
    author = re.sub(r'[\(（\[【].*?[\)）\]】]', '', author)
    author = re.sub(r'\s+', ' ', author).strip()
    if len(author) > 20 or re.search(r'\d{5,}', author) or author.lower() in ['unknown', 'xjdcn', '未知', '佚名', 'admin']:
        return ""
    return author

def extract_title_author_from_filename(filename):
    """从常见文件名模式中精准提取（书名，作者）"""
    base = os.path.splitext(filename)[0]
    base = re.sub(r'^(?:\[[^\]]+\]|【[^】]+】|\d+[\.\-\s_、]+)+', '', base).strip()

    m = re.match(r'^《([^》]+)》\s*(.*)$', base)
    if m:
        t = m.group(1).strip()
        raw_a = m.group(2).strip()
        raw_a = re.sub(r'【[^】]*】', '', raw_a)
        raw_a = re.sub(r'（[^）]*豆瓣[^）]*）', '', raw_a)
        raw_a = re.sub(r'\([^)]*豆瓣[^)]*\)', '', raw_a)
        raw_a = re.sub(r'v\d+[\.\d]*', '', raw_a, flags=re.I)
        raw_a = re.sub(r'^(?:作者[:：]|著[:：]|编[:：])', '', raw_a).strip()
        return t, clean_author_name(raw_a)

    if ' - ' in base or ' – ' in base or '—' in base:
        parts = re.split(r'\s*[\-–—]\s*', base, maxsplit=1)
        if len(parts) == 2:
            return parts[0].strip(), clean_author_name(parts[1])

    return base, ""

def clean_title_for_search(filename, epub_title=""):
    raw = filename
    fn_t, _ = extract_title_author_from_filename(filename)
    if fn_t and fn_t != os.path.splitext(filename)[0]:
        raw = fn_t
    elif epub_title and len(epub_title) <= 40:
        raw = epub_title

    base = os.path.splitext(raw)[0]
    base = re.sub(r'^\d+[\.\-\s_、]+', '', base)
    base = base.replace('《', '').replace('》', '')
    base = re.sub(r'【[^】]*】', ' ', base)
    base = re.sub(r'\[[^\]]*\]', ' ', base)
    
    series_words = '文丛|丛书|系列|文库|译丛|收获|新版|精装|平装|插图|典藏|全本|全集|套装|校对|三联|商务|人邮|中华书局'
    base = re.sub(r'（[^）]*(?:' + series_words + r')[^）]*）', ' ', base)
    base = re.sub(r'\([^)]*(?:' + series_words + r')[^)]*\)', ' ', base)
    
    marketing_words = '畅销|重磅|独家|精选|千万册|一定要读|一生|经典|必读|刷屏|硬核|战争|大陆唯一|大陆|首度|电视剧|原著|透彻|校对版|精编|全国通识|年度榜|名家|生命的奇迹|偶像与血|作品精选'
    base = re.sub(r'（[^）]*(?:' + marketing_words + r')[^）]*）', ' ', base)
    base = re.sub(r'\([^)]*(?:' + marketing_words + r')[^)]*\)', ' ', base)
    
    base = re.sub(r'（[^）]{10,}）', ' ', base)
    base = re.sub(r'\([^)]{10,}\)', ' ', base)
    base = re.sub(r'作者[:：].*$', '', base)
    base = re.sub(r'^\-+', '', base)
    return ' '.join(base.split()).strip()

def check_is_collection(filename, title=""):
    combined = f"{filename} {title}"
    for kw in config.COLLECTION_KEYWORDS:
        if kw in combined:
            return True, f"匹配合集关键词: '{kw}'"
    for r in config.COLLECTION_REGEXES:
        m = r.search(combined)
        if m:
            return True, f"匹配合集规则: '{m.group(0)}'"
    return False, ""

def extract_epub_metadata(epub_path):
    info = {
        'title': '',
        'creator': '',
        'publisher': '',
        'pubdate': '',
        'isbn': '',
        'description': '',
        'cover_image': None,
        'internal_isbns': []
    }
    if not os.path.exists(epub_path) or not epub_path.lower().endswith('.epub'):
        return info

    try:
        # 直接全文扫描有效出版ISBN
        internal_isbns = scan_isbns_from_file(epub_path)
        info['internal_isbns'] = sorted(list(internal_isbns))
        if len(internal_isbns) == 1:
            info['isbn'] = info['internal_isbns'][0]

        with zipfile.ZipFile(epub_path, 'r') as z:
            opf_names = [n for n in z.namelist() if n.endswith('.opf')]
            if not opf_names:
                return info
            
            opf_name = opf_names[0]
            opf_dir = os.path.dirname(opf_name)
            opf_data = z.read(opf_name).decode('utf-8', errors='ignore')
            root = ET.fromstring(opf_data)

            ns = {
                'dc': 'http://purl.org/dc/elements/1.1/',
                'opf': 'http://www.idpf.org/2007/opf'
            }

            titles = [e.text for e in root.findall('.//dc:title', ns) if e.text]
            creators = [e.text for e in root.findall('.//dc:creator', ns) if e.text]
            pubs = [e.text for e in root.findall('.//dc:publisher', ns) if e.text]
            dates = [e.text for e in root.findall('.//dc:date', ns) if e.text]
            descs = [e.text for e in root.findall('.//dc:description', ns) if e.text]

            info['title'] = titles[0].strip() if titles else ''
            info['creator'] = clean_author_name(creators[0]) if creators else ''
            info['publisher'] = pubs[0].strip() if pubs else ''
            info['pubdate'] = dates[0].strip() if dates else ''
            info['description'] = descs[0].strip() if descs else ''

            # 如果未从全文获取到单条ISBN，尝试从dc:identifier补充
            if not info['isbn']:
                for elem in root.findall('.//dc:identifier', ns):
                    raw_id = (elem.text or '').strip()
                    clean_id = raw_id.replace('-', '').replace(' ', '')
                    if is_valid_isbn(clean_id):
                        info['isbn'] = isbn10_to_isbn13(clean_id)
                        break

            # 提取内嵌封面图片
            cover_href = None
            for m in root.findall('.//opf:meta', ns) + root.findall('.//meta'):
                if m.attrib.get('name') == 'cover':
                    cid = m.attrib.get('content')
                    for item in root.findall('.//opf:item', ns) + root.findall('.//item'):
                        if item.attrib.get('id') == cid:
                            cover_href = item.attrib.get('href')
                            break
                    if cover_href:
                        break

            if not cover_href:
                for ref in root.findall('.//opf:reference', ns) + root.findall('.//reference'):
                    if ref.attrib.get('type') == 'cover':
                        cover_href = ref.attrib.get('href')
                        break

            img_names = [n for n in z.namelist() if n.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
            resolved_cover_path = None
            if cover_href:
                cand = os.path.normpath(os.path.join(opf_dir, cover_href)).replace('\\', '/')
                if cand in z.namelist():
                    resolved_cover_path = cand

            if not resolved_cover_path:
                for n in img_names:
                    if 'cover' in n.lower():
                        resolved_cover_path = n
                        break

            if resolved_cover_path and resolved_cover_path in z.namelist():
                img_bytes = z.read(resolved_cover_path)
                try:
                    im = Image.open(io.BytesIO(img_bytes))
                    if im.mode != 'RGB':
                        im = im.convert('RGB')
                    info['cover_image'] = im
                except Exception:
                    pass

    except Exception:
        pass

    return info
