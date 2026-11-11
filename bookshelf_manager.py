# -*- coding: utf-8 -*-
"""
Bookshelf Manager - 书架数据管理、扫描、封面处理、预览与元数据处理模块
"""
import os
import sys
import json
import re
import shutil
import zipfile
import subprocess
from xml.etree import ElementTree as ET
from PIL import Image, ImageDraw, ImageFont

# 支持的电子书扩展名

def get_system_font(size=11):
    candidates = [
        "msyh.ttc", "msyhl.ttc", "simhei.ttf", "simsun.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "wqy-microhei.ttc", "NotoSansCJK-Regular.ttc"
    ]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()

BOOK_EXTENSIONS = {'.epub', '.azw3', '.azw', '.mobi', '.pdf', '.txt', '.djvu', '.cbz', '.cbr', '.fb2'}

_COVER_CACHE = {}

def format_file_size(size_bytes):
    """友好格式化文件大小"""
    if not size_bytes or size_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}" if unit in ['MB', 'GB'] else f"{int(size_bytes)} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"

def clean_html_tags(text):
    """去除 HTML 标签，保留纯文本简介"""
    if not text:
        return ""
    text = re.sub(r'<\s*br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</\s*p\s*>', '\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<[^>]+>', '', text)
    entities = {
        '&nbsp;': ' ', '&quot;': '"', '&amp;': '&',
        '&lt;': '<', '&gt;': '>', '&apos;': "'", '&#39;': "'"
    }
    for ent, char in entities.items():
        text = text.replace(ent, char)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def parse_folder_name(folder_name):
    """从规范目录名中提取书名、作者与ISBN（兼容 书名（作者）{isbn-xxx}）"""
    title = folder_name
    author = "未知作者"
    isbn = ""

    # 提取 isbn
    isbn_m = re.search(r'\{isbn-([^}]+)\}', folder_name, re.IGNORECASE)
    if isbn_m:
        isbn = isbn_m.group(1).strip()
        title = title[:isbn_m.start()].strip()

    # 提取作者：书名（作者） 或 书名(作者)
    author_m = re.search(r'[（\(]([^（\(\)）]+)[）\)]$', title)
    if author_m:
        author = author_m.group(1).strip()
        title = title[:author_m.start()].strip()

    return title, author, isbn

def parse_opf_file(opf_path):
    """解析 Calibre / EPUB 标准 OPF 文件元数据"""
    meta = {}
    try:
        tree = ET.parse(opf_path)
        root = tree.getroot()
        ns = {
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }

        title_el = root.find('.//dc:title', ns)
        if title_el is not None and title_el.text:
            meta['title'] = title_el.text.strip()

        creator_el = root.find('.//dc:creator', ns)
        if creator_el is not None and creator_el.text:
            meta['creator'] = creator_el.text.strip()

        pub_el = root.find('.//dc:publisher', ns)
        if pub_el is not None and pub_el.text:
            meta['publisher'] = pub_el.text.strip()

        date_el = root.find('.//dc:date', ns)
        if date_el is not None and date_el.text:
            d_val = date_el.text.strip()
            meta['pubdate'] = d_val.split('T')[0] if 'T' in d_val else d_val

        desc_el = root.find('.//dc:description', ns)
        if desc_el is not None and desc_el.text:
            meta['description'] = desc_el.text.strip()

        for id_el in root.findall('.//dc:identifier', ns):
            scheme = id_el.get(f'{{{ns["opf"]}}}scheme', '').lower()
            text = (id_el.text or '').strip()
            if scheme == 'isbn' or 'isbn' in id_el.attrib.get('id', '').lower():
                meta['isbn'] = text
                break
            elif re.match(r'^97[89]\d{10}$', text.replace('-', '')):
                meta['isbn'] = text
                break

        subjects = [s.text.strip() for s in root.findall('.//dc:subject', ns) if s.text]
        if subjects:
            meta['tags'] = subjects

    except Exception:
        pass
    return meta

class BookItem:
    def __init__(self, folder_path, file_path=None):
        self.folder_path = folder_path
        self.file_path = file_path
        self.title = ""
        self.author = ""
        self.isbn = ""
        self.publisher = ""
        self.pubdate = ""
        self.description = ""
        self.tags = []
        self.format = ""
        self.file_size = 0
        self.file_size_str = "0 B"
        self.cover_path = None
        self.all_files = []

    def to_dict(self):
        return {
            'folder_path': self.folder_path,
            'file_path': self.file_path,
            'title': self.title,
            'author': self.author,
            'isbn': self.isbn,
            'publisher': self.publisher,
            'pubdate': self.pubdate,
            'description': self.description,
            'tags': self.tags,
            'format': self.format,
            'file_size': self.file_size,
            'file_size_str': self.file_size_str,
            'cover_path': self.cover_path,
        }

def scan_book_folder(folder_path):
    """扫描单本图书目录，提取完整元数据与图书主文件"""
    if not os.path.isdir(folder_path):
        return None

    try:
        entries = os.listdir(folder_path)
    except Exception:
        return None

    book_files = []
    opf_files = []
    json_meta_path = None
    cover_candidates = []

    for name in entries:
        full_path = os.path.join(folder_path, name)
        if not os.path.isfile(full_path):
            continue
        ext = os.path.splitext(name)[1].lower()
        if ext in BOOK_EXTENSIONS:
            book_files.append((full_path, ext, os.path.getsize(full_path)))
        elif ext == '.opf':
            opf_files.append(full_path)
        elif name.lower() == 'metadata.json':
            json_meta_path = full_path
        elif ext in ['.jpg', '.jpeg', '.png', '.webp']:
            cover_candidates.append(full_path)

    if not book_files:
        return None

    def sort_key(item):
        ext = item[1]
        sz = item[2]
        priority = 0
        if ext == '.epub': priority = 10
        elif ext in ['.azw3', '.mobi']: priority = 8
        elif ext == '.pdf': priority = 6
        elif ext == '.txt': priority = 4
        return (priority, sz)

    book_files.sort(key=sort_key, reverse=True)
    primary_file, primary_ext, primary_size = book_files[0]

    book = BookItem(folder_path, primary_file)
    book.format = primary_ext[1:].upper()
    book.file_size = primary_size
    book.file_size_str = format_file_size(primary_size)
    book.all_files = [item[0] for item in book_files]

    for c in cover_candidates:
        c_base = os.path.basename(c).lower()
        if 'cover' in c_base:
            book.cover_path = c
            break
    if not book.cover_path and cover_candidates:
        book.cover_path = cover_candidates[0]

    folder_name = os.path.basename(folder_path)
    def_title, def_author, def_isbn = parse_folder_name(folder_name)
    book.title = def_title
    book.author = def_author
    book.isbn = def_isbn

    if json_meta_path:
        try:
            with open(json_meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
                if meta.get('title'): book.title = str(meta['title']).strip()
                if meta.get('creator'): book.author = str(meta['creator']).strip()
                if meta.get('isbn'): book.isbn = str(meta['isbn']).strip()
                if meta.get('publisher'): book.publisher = str(meta['publisher']).strip()
                if meta.get('pubdate'):
                    pd = str(meta['pubdate']).split('T')[0]
                    book.pubdate = pd
                if meta.get('description'):
                    book.description = clean_html_tags(meta['description'])
                if meta.get('tags'):
                    book.tags = meta['tags'] if isinstance(meta['tags'], list) else [meta['tags']]
        except Exception:
            pass

    if (not book.publisher or not book.description or not book.isbn) and opf_files:
        opf_meta = parse_opf_file(opf_files[0])
        if not book.title and opf_meta.get('title'): book.title = opf_meta['title']
        if not book.author and opf_meta.get('creator'): book.author = opf_meta['creator']
        if not book.isbn and opf_meta.get('isbn'): book.isbn = opf_meta['isbn']
        if not book.publisher and opf_meta.get('publisher'): book.publisher = opf_meta['publisher']
        if not book.pubdate and opf_meta.get('pubdate'): book.pubdate = opf_meta['pubdate']
        if not book.description and opf_meta.get('description'):
            book.description = clean_html_tags(opf_meta['description'])

    return book

def scan_library(library_dir):
    """扫描整个书库目录，返回所有书籍列表"""
    books = []
    if not os.path.exists(library_dir) or not os.path.isdir(library_dir):
        return books

    try:
        entries = os.listdir(library_dir)
    except Exception:
        return books

    # 1. 扫描直接子目录
    for name in entries:
        sub_path = os.path.join(library_dir, name)
        if os.path.isdir(sub_path):
            b = scan_book_folder(sub_path)
            if b:
                books.append(b)
            else:
                try:
                    for sub2 in os.listdir(sub_path):
                        sub2_path = os.path.join(sub_path, sub2)
                        if os.path.isdir(sub2_path):
                            b2 = scan_book_folder(sub2_path)
                            if b2:
                                books.append(b2)
                except Exception:
                    pass

    # 2. 扫描根目录下的散装电子书
    for name in entries:
        file_path = os.path.join(library_dir, name)
        if os.path.isfile(file_path):
            ext = os.path.splitext(name)[1].lower()
            if ext in BOOK_EXTENSIONS:
                sz = os.path.getsize(file_path)
                b = BookItem(library_dir, file_path)
                b_name = os.path.splitext(name)[0]
                t, a, i = parse_folder_name(b_name)
                b.title = t
                b.author = a
                b.isbn = i
                b.format = ext[1:].upper()
                b.file_size = sz
                b.file_size_str = format_file_size(sz)
                b.all_files = [file_path]
                books.append(b)

    books.sort(key=lambda x: x.title.lower())
    return books

def open_book_file(file_path):
    """调用系统默认程序打开图书文件进行阅读"""
    if not file_path or not os.path.exists(file_path):
        return False, "文件不存在"
    try:
        os.startfile(file_path)
        return True, "成功打开"
    except Exception as e:
        return False, str(e)

def open_folder_in_explorer(folder_path, highlight_file=None):
    """在 Windows 资源管理器中打开文件夹并选中文件"""
    if highlight_file and os.path.exists(highlight_file):
        try:
            norm_file = os.path.normpath(highlight_file)
            subprocess.run(f'explorer /select,"{norm_file}"', shell=True, check=False)
            return True
        except Exception:
            pass
    if os.path.exists(folder_path):
        try:
            os.startfile(folder_path)
            return True
        except Exception:
            pass
    return False

def delete_book_item(book_item):
    """从书库中删除图书及其目录文件"""
    if not book_item:
        return False, "无效图书"
    try:
        folder = book_item.folder_path
        if os.path.isdir(folder) and os.path.basename(folder):
            shutil.rmtree(folder)
            return True, "已成功删除图书目录"
        elif book_item.file_path and os.path.exists(book_item.file_path):
            os.remove(book_item.file_path)
            return True, "已成功删除图书文件"
        return False, "未能定位待删除的目标"
    except Exception as e:
        return False, f"删除失败: {e}"

def update_book_metadata(book_item, new_meta):
    """更新图书的元数据并写回 metadata.json 与 .opf"""
    if not book_item or not book_item.folder_path:
        return False, "无效图书"
    folder = book_item.folder_path
    if not os.path.isdir(folder):
        return False, "图书所在目录不存在"

    for key, val in new_meta.items():
        if hasattr(book_item, key):
            setattr(book_item, key, val)

    meta_json_path = os.path.join(folder, "metadata.json")
    json_data = {
        "title": book_item.title,
        "creator": book_item.author,
        "isbn": book_item.isbn,
        "publisher": book_item.publisher,
        "pubdate": book_item.pubdate,
        "language": "zho",
        "description": book_item.description,
        "tags": book_item.tags
    }
    try:
        with open(meta_json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        return False, f"写入 metadata.json 失败: {e}"

    try:
        from opf_generator import generate_calibre_opf
        opf_path = os.path.join(folder, f"{book_item.title}-{book_item.author}.opf")
        generate_calibre_opf(json_data, opf_path, cover_filename="cover.jpg")
    except Exception:
        pass

    return True, "元数据更新成功"

def extract_book_preview(file_path):
    """提取图书章节或前部分文本，用于内置快速预览阅读"""
    if not file_path or not os.path.exists(file_path):
        return [("错误", "文件不存在")]

    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.epub':
        chapters = []
        try:
            with zipfile.ZipFile(file_path, 'r') as zf:
                html_files = [n for n in zf.namelist() if n.lower().endswith(('.html', '.xhtml', '.htm'))]
                for name in html_files:
                    raw = zf.read(name).decode('utf-8', errors='ignore')
                    txt = clean_html_tags(raw)
                    if len(txt) > 30:
                        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
                        title = lines[0] if lines else os.path.basename(name)
                        if len(title) > 30:
                            title = title[:28] + "..."
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
                return [("读取失败", "未能识别文本编码")]

            chap_pattern = re.compile(r'^(第[0-9一二三四五六七八九十百千]+[章回节卷集部].*)$', re.M)
            matches = list(chap_pattern.finditer(content))
            if len(matches) >= 2:
                chapters = []
                for i, m in enumerate(matches):
                    chap_title = m.group(1).strip()
                    start = m.start()
                    end = matches[i+1].start() if i + 1 < len(matches) else len(content)
                    chap_txt = content[start:end].strip()
                    chapters.append((chap_title, chap_txt))
                return chapters
            else:
                return [("正文", content)]
        except Exception as e:
            return [("错误", str(e))]

    else:
        return [("说明", f"当前格式 [{ext.upper()}] 建议使用【立即打开观看】调用系统阅读器欣赏。")]

def make_zlib_thumbnail(cover_path, title, author, badge_text="阅读", target_size=(150, 218)):
    """制作 Z-Library 风格高质感封面缩略图（带半透明青色圆角徽章与深色画框）"""
    cache_key = (cover_path, title, badge_text, target_size)
    if cache_key in _COVER_CACHE:
        return _COVER_CACHE[cache_key]

    tw, th = target_size
    if cover_path and os.path.exists(cover_path):
        try:
            im = Image.open(cover_path).convert("RGBA")
            im.thumbnail((tw, th), Image.Resampling.LANCZOS)
            base = Image.new("RGBA", (tw, th), (24, 28, 38, 255))
            ox = (tw - im.width) // 2
            oy = (th - im.height) // 2
            base.paste(im, (ox, oy), im)
        except Exception:
            base = create_fallback_cover(title, author, target_size)
    else:
        base = create_fallback_cover(title, author, target_size)

    base = base.convert("RGBA")
    overlay = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # 绘制外边框细线
    draw.rectangle([0, 0, tw - 1, th - 1], outline=(42, 50, 75, 200), width=1)

    # 绘制右下角青色胶囊徽章 (参考截图中的 '下载' / 'Downloaded' 按钮风格)
    bw, bh = 46, 20
    bx1 = tw - bw - 5
    by1 = th - bh - 5
    bx2 = tw - 5
    by2 = th - 5

    draw.rounded_rectangle([bx1, by1, bx2, by2], radius=4, fill=(8, 145, 178, 235))

    font = get_system_font(11)

    bbox = font.getbbox(badge_text)
    fw = bbox[2] - bbox[0]
    fh = bbox[3] - bbox[1]
    fx = bx1 + (bw - fw) // 2
    fy = by1 + (bh - fh) // 2
    draw.text((fx, fy), badge_text, font=font, fill=(255, 255, 255, 255))

    final_img = Image.alpha_composite(base, overlay).convert("RGB")
    _COVER_CACHE[cache_key] = final_img
    return final_img

def create_fallback_cover(title, author, size):
    """绘制精致无封面占位卡片"""
    tw, th = size
    im = Image.new("RGBA", (tw, th), (27, 33, 48, 255))
    draw = ImageDraw.Draw(im)
    draw.rectangle([6, 6, tw - 7, th - 7], outline=(47, 57, 82, 255), width=2)
    f_title = get_system_font(13)
    f_author = get_system_font(10)
    f_icon = get_system_font(22)

    # 绘制书本图标
    draw.text((tw // 2 - 12, 35), "📖", font=f_icon, fill=(56, 189, 248, 220))

    # 标题折行显示
    short_title = title if len(title) <= 8 else (title[:7] + "...")
    draw.text((16, 85), short_title, font=f_title, fill=(241, 245, 249, 255))
    draw.text((16, 115), author[:10] if author else "未知作者", font=f_author, fill=(148, 163, 184, 255))
    return im
