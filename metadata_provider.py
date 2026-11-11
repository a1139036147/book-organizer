# -*- coding: utf-8 -*-
"""
Metadata Provider for Book Organizer
Dual-track architecture:
  - Track A (Option 2): Native pure-Python providers (Douban, WeRead, Google Books, Open Library, Bangumi)
  - Track B (Option 3): Calibre plugin shim & loader (runs drop-in Calibre community .zip/.py plugins)
"""
import urllib.request
import urllib.parse
import threading

# 修复打包环境下 ssl 缺少 codex-rejected-cas.pem 导致的 [Errno 2] 崩溃
try:
    import ssl, os, sys
    _orig_ssl_new = ssl.SSLContext.__new__
    def _safe_ssl_context_new(cls, *args, **kwargs):
        try:
            return _orig_ssl_new(cls, *args, **kwargs)
        except FileNotFoundError:
            return ssl._SSLContext.__new__(cls, *args, **kwargs)
    ssl.SSLContext.__new__ = _safe_ssl_context_new

    if getattr(sys, 'frozen', False):
        try:
            meipass = getattr(sys, '_MEIPASS', '')
            if meipass:
                pem_path = os.path.join(meipass, 'codex-rejected-cas.pem')
                if not os.path.exists(pem_path):
                    with open(pem_path, 'wb') as f:
                        pass
        except Exception:
            pass
except Exception:
    pass

import http.cookiejar
import random
import string
import json
import time
import re
import io
from lxml import html
from PIL import Image

import config
import calibre_shim
import epub_handler

GENERIC_WORDS = [
    r'三部曲', r'四部曲', r'二部曲', r'五部曲', r'套装', r'合集', r'全集',
    r'文集', r'作品集', r'丛书', r'系列', r'精选', r'严选',
    r'共\s*\d+\s*[册卷本部]', r'全\s*\d+\s*[册卷本部]', r'第\s*[0-9一二三四五六七八九十]+\s*[册卷本部]',
    r'典藏版', r'纪念版', r'修订版', r'完整版', r'经典版', r'珍藏版'
]

def clean_html_text(val):
    if not val:
        return ""
    val = re.sub(r'<[^>]+>', ' ', val)
    return ' '.join(val.split()).strip(' :：')

def strip_generic_words(text):
    if not text:
        return ""
    t = re.sub(r'[\(（\[【〔].*?[\)）\]】〕]', '', text)
    for g in GENERIC_WORDS:
        t = re.sub(g, '', t)
    t = re.sub(r'[^\w\u4e00-\u9fa5]', '', t)
    return t.strip()

CN_TO_ARABIC_MAP = {'〇':'0', '零':'0', '一':'1', '二':'2', '两':'2', '三':'3', '四':'4', '五':'5', '六':'6', '七':'7', '八':'8', '九':'9'}
ARABIC_TO_CN_MAP = {'0':'〇','1':'一','2':'二','3':'三','4':'四','5':'五','6':'六','7':'七','8':'八','9':'九'}

def normalize_year_digits(text):
    if not text: return ""
    def cn_to_ar(m):
        return ''.join(CN_TO_ARABIC_MAP.get(c, c) for c in m.group(0))
    # 转换 中文年份 -> 阿拉伯年份 (如 一九三四 -> 1934, 二〇六一 -> 2061)
    res = re.sub(r'[〇零一二两三四五六七八九]{4}', cn_to_ar, text)
    return res

def convert_year_numbers(text):
    if not text: return ""
    def rep(m):
        return ''.join(ARABIC_TO_CN_MAP.get(c, c) for c in m.group(0))
    return re.sub(r'(18\d{2}|19\d{2}|20\d{2})', rep, text)

def author_matches(q_author, r_author):
    if not q_author or q_author.lower() in ['unknown', '未知', '佚名', 'xjdcn']:
        return True
    if not r_author:
        return True
    clean_q = re.sub(r'[\(（\[【].*?[\)）\]】]', '', q_author)
    clean_r = re.sub(r'[\(（\[【].*?[\)）\]】]', '', r_author)
    clean_q = re.sub(r'[^\w\u4e00-\u9fa5]', '', clean_q)
    clean_r = re.sub(r'[^\w\u4e00-\u9fa5]', '', clean_r)
    if not clean_q or not clean_r:
        return True
    return clean_q in clean_r or clean_r in clean_q

def does_title_correspond(target_title, result_title, author_query="", author_result=""):
    """
    验证网络返回的图书标题是否与当前电子书名对应。
    支持多卷本/全集识别（如《草婴译著全集·第一卷》或《草婴译著全集（全12卷）》均对应《草婴译著全集》；
    《半泽直树 1》对应《半泽直树》）。
    反之，《证券分析的方法》与《巴菲特的投资理财课》不对应。
    """
    if not target_title or not result_title:
        return False

    core_target = normalize_year_digits(strip_generic_words(target_title))
    core_result = normalize_year_digits(strip_generic_words(result_title))
    if not core_target or not core_result:
        return False

    # 1. 核心标题完全包含关系（当主干长度>=3时直接判定匹配，容忍原作者 vs 译者差异）
    if (len(core_target) >= 3 and core_target in core_result) or (len(core_result) >= 3 and core_result in core_target):
        return True

    # 2. 分隔符切分主标题（冒号、中间点、短横线、空格）
    p_target = re.split(r'[:：·\-\s]', target_title)[0].strip()
    p_result = re.split(r'[:：·\-\s]', result_title)[0].strip()
    c_p_target = strip_generic_words(p_target)
    c_p_result = strip_generic_words(p_result)
    if c_p_target and c_p_result:
        if (len(c_p_target) >= 3 and c_p_target in c_p_result) or (len(c_p_result) >= 3 and c_p_result in c_p_target):
            return True

    # 3. 模糊匹配必须作者兼容
    if not author_matches(author_query, author_result):
        return False

    return is_title_match(target_title, result_title, author_query=author_query, author_result=author_result)

def is_collection_title_match(clean_title, result_title):
    """
    验证网络返回的标题是否本身就是合集/套装的出版标题（而非仅仅其中单独一本分册）。
    例如《草婴译著全集》对应《草婴译著全集》，而《草婴译著全集·第一卷》属于分卷。
    """
    if not clean_title or not result_title:
        return False
    core_clean = strip_generic_words(clean_title)
    core_result = strip_generic_words(result_title)
    if not core_clean or not core_result:
        return False
    if core_clean == core_result:
        return True
    if len(core_clean) >= 3 and (core_clean in core_result or core_result in core_clean):
        if len(core_clean) <= len(core_result) + 4 and len(core_result) <= len(core_clean) + 4:
            return True
    return False

def is_title_match(query_title, result_title, author_query="", author_result=""):
    # 1. 如果有作者提示，首先校验作者是否冲突
    if not author_matches(author_query, author_result):
        return False

    core_q = strip_generic_words(query_title)
    core_r = strip_generic_words(result_title)
    if not core_q or not core_r:
        return False

    # 提取主标题（剔除副标题或从属说明）
    primary_r = re.split(r'[:：\-·\s]', result_title)[0]
    primary_r_core = strip_generic_words(primary_r)

    # 2. 如果主标题直接包含或被包含
    if (core_q in core_r or core_r in core_q) and (primary_r_core and (core_q in primary_r_core or primary_r_core in core_q)):
        return True

    set_q = set(core_q)
    set_r = set(core_r)
    common = set_q & set_r
    if not common:
        return False

    ratio = len(common) / len(set_q)
    return ratio >= 0.7

def download_cover_from_url(cover_url, delay=1.0):
    """通用的封面大图下载与转换函数，自适应不同站点的 Anti-hotlinking 与 User-Agent"""
    if not cover_url:
        return None
    headers = {
        'User-Agent': config.HTTP_HEADERS.get('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),
        'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'
    }
    if 'douban' in cover_url or 'doubanio' in cover_url:
        headers['Referer'] = 'https://book.douban.com/'
    elif 'weread' in cover_url:
        headers['Referer'] = 'https://weread.qq.com/'

    req = urllib.request.Request(cover_url, headers=headers)
    try:
        with self.opener.open(req, timeout=config.REQUEST_TIMEOUT) as resp:
            data = resp.read()
        im = Image.open(io.BytesIO(data))
        if im.mode != 'RGB':
            im = im.convert('RGB')
        return im
    except Exception:
        return None

# ---------------------------------------------------------------------------
# Track A (Option 2): Native Pure-Python Providers
# ---------------------------------------------------------------------------

class DoubanProvider:
    """中文元数据第一站（参考并提炼自 Calibre 社区豆瓣插件核心）"""
    def __init__(self, delay=config.REQUEST_DELAY):
        self.delay = delay
        self.last_request_time = 0
        self.rate_lock = threading.Lock()
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))
        self.bid = ''.join(random.choices(string.ascii_letters + string.digits, k=11))

    def _get_headers(self):
        return {
            'User-Agent': config.HTTP_HEADERS.get('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Cookie': f'bid="{self.bid}"; ll="108288"',
            'Referer': 'https://book.douban.com/'
        }
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookie_jar))

    def _get_headers(self, referer="https://book.douban.com/"):
        headers = dict(config.HTTP_HEADERS)
        headers['Referer'] = referer
        return headers

    def _rate_limit(self):
        with self.rate_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_request_time = time.time()

    def search(self, keyword):
        if not keyword:
            return []
        self._rate_limit()
        q = urllib.parse.quote(keyword.strip())
        seen = set()
        unique_sids = []

        # 优先使用豆瓣官方轻量 subject_suggest 接口获取 subject id
        try:
            sug_url = f"https://book.douban.com/j/subject_suggest?q={q}"
            sug_req = urllib.request.Request(sug_url, headers=config.HTTP_HEADERS)
            with urllib.request.urlopen(sug_req, timeout=5) as sug_resp:
                sug_data = json.loads(sug_resp.read().decode('utf-8'))
                for item in sug_data:
                    item_id = str(item.get('id', '')).strip()
                    if item_id and item_id not in seen:
                        seen.add(item_id)
                        unique_sids.append(item_id)
        except Exception:
            pass

        try:
            url = f"https://www.douban.com/search?cat=1001&q={q}"
            req = urllib.request.Request(url, headers=self._get_headers(referer="https://www.douban.com/"))
            with self.opener.open(req, timeout=config.REQUEST_TIMEOUT) as resp:
                page = resp.read().decode('utf-8', errors='ignore')
            sids = re.findall(r'sid:\s*(\d+)', page)
            for s in sids:
                if s not in seen:
                    seen.add(s)
                    unique_sids.append(s)
        except Exception:
            pass
        return unique_sids

    def get_subject_details(self, sid):
        if not sid:
            return None
        self._rate_limit()
        try:
            url = f"https://book.douban.com/subject/{sid}/"
            req = urllib.request.Request(url, headers=self._get_headers(referer="https://book.douban.com/"))
            with self.opener.open(req, timeout=config.REQUEST_TIMEOUT) as resp:
                page = resp.read().decode('utf-8', errors='ignore')
        except Exception:
            return None

        try:
            tree = html.fromstring(page)
            t_nodes = tree.xpath('//span[@property="v:itemreviewed"]/text()')
            title = t_nodes[0].strip() if t_nodes else ''
            if not title:
                return None

            info_divs = tree.xpath('//div[@id="info"]')
            info_div = info_divs[0] if info_divs else None

            def get_field(label):
                if info_div is None:
                    return ''
                nodes = info_div.xpath(f'.//span[contains(@class, "pl") and contains(text(), "{label}")]')
                if not nodes:
                    return ''
                node = nodes[0]
                res = []
                for sib in node.xpath('./following-sibling::*'):
                    if 'pl' in sib.attrib.get('class', ''):
                        break
                    if sib.tag == 'br':
                        break
                    res.append(sib.text_content().strip())
                    if sib.tail:
                        res.append(sib.tail.strip())
                if node.tail and node.tail.strip():
                    res.insert(0, node.tail.strip())
                return ' '.join([r for r in res if r]).strip(' :：')

            author = get_field('作者')
            publisher = get_field('出版社')
            pubdate = get_field('出版年')
            isbn = get_field('ISBN').replace('-', '').strip()

            cover_nodes = tree.xpath('//a[@class="nbg"]/@href')
            cover_url = cover_nodes[0] if cover_nodes else ''
            if cover_url.startswith('//'):
                cover_url = 'https:' + cover_url
            cover_url = cover_url.replace('/s/public/', '/l/public/').replace('/m/public/', '/l/public/')

            desc_nodes = tree.xpath('//div[contains(@class, "intro")]')
            desc_html = ''
            if desc_nodes:
                desc_html = html.tostring(desc_nodes[0], encoding='utf-8').decode('utf-8').strip()

            rating_nodes = tree.xpath('//strong[contains(@class, "rating_num")]/text()')
            rating = rating_nodes[0].strip() if rating_nodes else '8.0'
            try:
                rating_val = int(round(float(rating)))
            except Exception:
                rating_val = 8

            tag_nodes = tree.xpath('//a[contains(@class, "tag")]/text() | //div[@id="db-tags-section"]//a/text()')
            tags = [t.strip() for t in tag_nodes if t.strip()]

            return {
                'source': 'douban',
                'douban_id': sid,
                'google_id': None,
                'title': title,
                'author': author,
                'publisher': publisher,
                'pubdate': pubdate,
                'isbn': isbn,
                'cover_url': cover_url,
                'description': desc_html,
                'rating': rating_val,
                'tags': tags
            }
        except Exception:
            return None

    def download_cover(self, cover_url):
        return download_cover_from_url(cover_url, delay=self.delay)


class WeReadProvider:
    """微信读书开放检索接口：中文正规出版物的高速直连源，提供高清封面"""
    def __init__(self, delay=config.REQUEST_DELAY):
        self.delay = delay
        self.last_request_time = 0
        self.rate_lock = threading.Lock()
        self.opener = urllib.request.build_opener()

    def _rate_limit(self):
        with self.rate_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_request_time = time.time()

    def search(self, query):
        if not query:
            return []
        self._rate_limit()
        q = urllib.parse.quote(query.strip())
        url = f"https://weread.qq.com/web/search/global?keyword={q}&maxIdx=0"
        req = urllib.request.Request(url, headers={
            'User-Agent': config.HTTP_HEADERS.get('User-Agent', 'Mozilla/5.0'),
            'Accept': 'application/json'
        })
        try:
            with self.opener.open(req, timeout=config.REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            books = data.get('books', [])
            results = []
            for item in books:
                b = item.get('bookInfo', {})
                title = b.get('title', '').strip()
                if not title:
                    continue
                author = b.get('author', '').strip()
                publisher = b.get('publisher', '').strip()
                intro = b.get('intro', '').strip()
                raw_cover = b.get('cover', '')
                # 微信读书高清图替换规则：/s_ -> /t6_
                cover_url = raw_cover.replace('/s_', '/t6_') if raw_cover else ''
                new_rating = b.get('newRating', 0)
                rating = int(round(new_rating / 100.0)) if new_rating else 8
                series_name = b.get('lPushName', '')
                tags = [series_name] if series_name else []

                results.append({
                    'source': 'weread',
                    'weread_id': b.get('bookId'),
                    'title': title,
                    'author': author,
                    'publisher': publisher,
                    'pubdate': '',
                    'isbn': '',
                    'cover_url': cover_url,
                    'description': intro,
                    'rating': rating,
                    'tags': tags
                })
            return results
        except Exception:
            return []


class OpenLibraryProvider:
    """提取自 Calibre 内置 Open Library 插件：全球外文书与公版书，免Key无反爬限制"""
    def __init__(self, delay=config.REQUEST_DELAY):
        self.delay = delay
        self.last_request_time = 0
        self.rate_lock = threading.Lock()
        self.opener = urllib.request.build_opener()

    def _rate_limit(self):
        with self.rate_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_request_time = time.time()

    def fetch_by_isbn(self, isbn):
        if not isbn:
            return None
        self._rate_limit()
        clean_isbn = isbn.replace('-', '').strip()
        url = f"https://openlibrary.org/api/books?bibkeys=ISBN:{clean_isbn}&format=json&jscmd=data"
        req = urllib.request.Request(url, headers={'User-Agent': 'BookOrganizer/2.0'})
        try:
            with self.opener.open(req, timeout=config.REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            key = f"ISBN:{clean_isbn}"
            if key not in data:
                return None
            book = data[key]
            title = book.get('title', '').strip()
            if not title:
                return None

            authors = ', '.join([a.get('name', '') for a in book.get('authors', []) if a.get('name')])
            publishers = ', '.join([p.get('name', '') for p in book.get('publishers', []) if p.get('name')])
            pubdate = book.get('publish_date', '')
            cover_info = book.get('cover', {})
            cover_url = cover_info.get('large') or cover_info.get('medium') or cover_info.get('small') or ''
            desc = book.get('notes', '') or book.get('subtitle', '')
            subjects = [s.get('name', '') for s in book.get('subjects', []) if s.get('name')][:8]

            return {
                'source': 'openlibrary',
                'title': title,
                'author': authors,
                'publisher': publishers,
                'pubdate': pubdate,
                'isbn': clean_isbn,
                'cover_url': cover_url,
                'description': desc,
                'rating': 8,
                'tags': subjects
            }
        except Exception:
            return None

    def search(self, query):
        if not query:
            return []
        self._rate_limit()
        q = urllib.parse.quote(query.strip())
        url = f"https://openlibrary.org/search.json?q={q}&limit=5"
        req = urllib.request.Request(url, headers={'User-Agent': 'BookOrganizer/2.0'})
        try:
            with self.opener.open(req, timeout=config.REQUEST_TIMEOUT) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            docs = data.get('docs', [])
            results = []
            for d in docs:
                title = d.get('title', '')
                if not title:
                    continue
                authors = ', '.join(d.get('author_name', []))
                publishers = ', '.join(d.get('publisher', [])[:2])
                pubdate = str(d.get('first_publish_year', ''))
                isbns = d.get('isbn', [])
                isbn = isbns[0].replace('-', '').strip() if isbns else ''
                cover_id = d.get('cover_i')
                cover_url = f"https://covers.openlibrary.org/b/id/{cover_id}-L.jpg" if cover_id else ''

                results.append({
                    'source': 'openlibrary',
                    'title': title,
                    'author': authors,
                    'publisher': publishers,
                    'pubdate': pubdate,
                    'isbn': isbn,
                    'cover_url': cover_url,
                    'description': '',
                    'rating': 8,
                    'tags': d.get('subject', [])[:5]
                })
            return results
        except Exception:
            return []


class BangumiProvider:
    """提取自 Calibre-Bangumi 社区插件：日系漫画、轻小说分卷权威元数据库"""
    def __init__(self, delay=config.REQUEST_DELAY):
        self.delay = delay
        self.last_request_time = 0
        self.rate_lock = threading.Lock()
        self.opener = urllib.request.build_opener()

    def _rate_limit(self):
        with self.rate_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_request_time = time.time()

    def search(self, title):
        if not title:
            return None
        self._rate_limit()
        q = urllib.parse.quote(title.strip())
        url = f"https://api.bgm.tv/search/subject/{q}?type=1&responseGroup=large"
        req = urllib.request.Request(url, headers={'User-Agent': 'BookOrganizer/2.0 (compatible)'})
        try:
            with self.opener.open(req, timeout=config.REQUEST_TIMEOUT) as resp:
                res = json.loads(resp.read().decode('utf-8'))
            items = res.get('list', [])
            if not items:
                return None
            item = items[0]
            score = item.get('rating', {}).get('score', 8)
            cover = item.get('images', {}).get('large') or item.get('images', {}).get('common') or ''
            return {
                'source': 'bangumi',
                'bangumi_id': item.get('id'),
                'title': item.get('name_cn') or item.get('name', ''),
                'author': '',
                'publisher': '',
                'pubdate': item.get('air_date', ''),
                'isbn': '',
                'cover_url': cover,
                'description': item.get('summary', ''),
                'rating': int(round(score)),
                'tags': ['ACG', '轻小说/漫画']
            }
        except Exception:
            return None


class GoogleBooksProvider:
    """全球官方图书索引库（支持个人 API Key 扩展高配额）"""
    def __init__(self, api_key=None, delay=config.REQUEST_DELAY):
        self.api_key = api_key
        self.delay = delay
        self.last_request_time = 0
        self.rate_lock = threading.Lock()
        self.opener = urllib.request.build_opener()

    def _rate_limit(self):
        with self.rate_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_request_time = time.time()

    def search(self, query):
        if not query:
            return []
        self._rate_limit()
        q = urllib.parse.quote(query.strip())
        url = f"https://www.googleapis.com/books/v1/volumes?q={q}"
        if self.api_key:
            url += f"&key={self.api_key}"
        req = urllib.request.Request(url, headers={'User-Agent': config.HTTP_HEADERS.get('User-Agent', 'Mozilla/5.0')})
        try:
            with self.opener.open(req, timeout=config.REQUEST_TIMEOUT) as resp:
                res = json.loads(resp.read().decode('utf-8'))
            items = res.get('items', [])
            results = []
            for item in items:
                v = item.get('volumeInfo', {})
                isbn = ''
                for ident in v.get('industryIdentifiers', []):
                    t = ident.get('type', '')
                    val = ident.get('identifier', '').replace('-', '').strip()
                    if 'ISBN_13' in t:
                        isbn = val
                        break
                    elif 'ISBN_10' in t and not isbn:
                        isbn = val

                img_links = v.get('imageLinks', {})
                cover_url = img_links.get('extraLarge') or img_links.get('large') or img_links.get('medium') or img_links.get('thumbnail') or ''
                if cover_url.startswith('http://'):
                    cover_url = 'https://' + cover_url[7:]

                authors = v.get('authors', [])
                author_str = ' & '.join(authors) if authors else ''

                results.append({
                    'source': 'google',
                    'google_id': item.get('id'),
                    'douban_id': None,
                    'title': v.get('title', ''),
                    'author': author_str,
                    'publisher': v.get('publisher', ''),
                    'pubdate': v.get('publishedDate', ''),
                    'isbn': isbn,
                    'cover_url': cover_url,
                    'description': v.get('description', ''),
                    'rating': int(round(v.get('averageRating', 8))),
                    'tags': v.get('categories', [])
                })
            return results
        except Exception:
            return []

    def download_cover(self, cover_url):
        return download_cover_from_url(cover_url, delay=self.delay)

# ---------------------------------------------------------------------------
# Dual-track Orchestration: UnifiedMetadataProvider
# ---------------------------------------------------------------------------

class DangDangProvider:
    """当当图书数据库（国内正版图书核心权威库，海量官方出版ISBN，抗封禁免Key）"""
    def __init__(self, delay=config.REQUEST_DELAY):
        self.delay = delay
        self.last_request_time = 0
        self.rate_lock = threading.Lock()
        self.headers = {
            'User-Agent': config.HTTP_HEADERS.get('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'
        }

    def _rate_limit(self):
        with self.rate_lock:
            elapsed = time.time() - self.last_request_time
            if elapsed < self.delay:
                time.sleep(self.delay - elapsed)
            self.last_request_time = time.time()

    def fetch_by_isbn(self, isbn):
        return self.fetch_by_query(isbn)

    def fetch_by_query(self, query):
        if not query:
            return None
        self._rate_limit()
        clean_q = re.sub(r'[\(（\[【].*?[\)）\]】]', '', query).strip()
        try:
            q_enc = urllib.parse.quote(clean_q, encoding='gbk')
        except Exception:
            q_enc = urllib.parse.quote(clean_q)

        url = f"http://search.dangdang.com/?key={q_enc}&act=input"
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req, timeout=6) as resp:
                content = resp.read().decode('gbk', errors='ignore')
        except Exception:
            return None

        try:
            tree = html.fromstring(content)
            items = tree.xpath('//li[contains(@class, "line") or contains(@id, "p_")]')
            if not items:
                return None

            # 策略 1: 直接从搜索结果卡片全文提取 ISBN（绝大多数当当商家标题均直接附带完整13位出版ISBN，秒级命中）
            for it in items[:15]:
                txt = ' '.join(it.xpath('.//text()'))
                isbns = re.findall(r'(97[89]\d{10})', txt)
                if isbns and epub_handler.is_valid_isbn(isbns[0]):
                    isbn = isbns[0]
                    # 封面
                    imgs = it.xpath('.//img/@data-original') or it.xpath('.//img/@src')
                    cover_url = imgs[0] if imgs else ''
                    if cover_url.startswith('//'): cover_url = 'http:' + cover_url
                    # 作者与出版社
                    a_nodes = it.xpath('.//span[@class="search_book_author"]//a[1]/@title') or it.xpath('.//span[@class="search_book_author"]//a[1]/text()')
                    author = epub_handler.clean_author_name(a_nodes[0].strip()) if a_nodes else ''
                    if not author:
                        m_a = re.search(r'(?:\[[^\]]+\]|【[^】]+】|（[^）]+）)?[一-龥·•a-zA-Z\s]{2,20}\s*(?:著|编|译)', txt)
                        if m_a:
                            author = re.sub(r'\s*(?:著|编|译).*$', '', m_a.group(0)).strip()
                            author = epub_handler.clean_author_name(author)
                    pub_nodes = it.xpath('.//span[@class="search_book_author"]//a[contains(@href, "publish")]/@title') or it.xpath('.//span[@class="search_book_author"]//a[contains(@href, "publish")]/text()')
                    pub = pub_nodes[0].strip() if pub_nodes else ''
                    return {
                        'source': 'dangdang',
                        'title': clean_q,
                        'author': author,
                        'publisher': pub,
                        'pubdate': '',
                        'isbn': isbn,
                        'cover_url': cover_url,
                        'description': '',
                        'rating': 9,
                        'tags': []
                    }

            # 策略 2: 访问详情页深度提取
            for item in items[:4]:
                link = item.xpath('.//a[@name="itemlist-title"]/@href') or item.xpath('.//a/@href')
                if not link:
                    continue
                p_url = link[0] if link[0].startswith('http') else 'http:' + link[0]
                if 'product.dangdang.com' not in p_url:
                    continue

                p_req = urllib.request.Request(p_url, headers=self.headers)
                try:
                    with urllib.request.urlopen(p_req, timeout=6) as p_resp:
                        p_html = p_resp.read().decode('gbk', errors='ignore')
                except Exception:
                    continue

                isbn_m = re.search(r'(?:国际标准书号|ISBN)[：:\s]*(\d{10,13})', p_html, re.I)
                if not isbn_m:
                    isbn_m = re.search(r'(97[89]\d{10})', p_html)
                if not isbn_m:
                    continue

                isbn = isbn_m.group(1).replace('-', '').strip()
                if not epub_handler.is_valid_isbn(isbn):
                    continue

                p_tree = html.fromstring(p_html)
                t_nodes = p_tree.xpath('//div[@class="name_info"]/h1/@title') or p_tree.xpath('//div[@class="name_info"]/h1/text()')
                raw_t = t_nodes[0].strip() if t_nodes else clean_q
                t_str = clean_q if clean_q in raw_t else raw_t.split('——')[0].split('【')[0].strip()

                a_nodes = p_tree.xpath('//span[@id="author"]//a/text()') or p_tree.xpath('//span[@id="author"]/text()')
                a_str = ', '.join([x.strip() for x in a_nodes if x.strip()])
                a_str = epub_handler.clean_author_name(a_str)

                pub_nodes = p_tree.xpath('//span[@dd_name="出版社"]//a/text()') or p_tree.xpath('//span[@dd_name="出版社"]/text()')
                pub_str = pub_nodes[0].strip() if pub_nodes else ''

                img_nodes = p_tree.xpath('//img[@id="largePic"]/@src') or p_tree.xpath('//img[@id="main-img-slider"]/@src')
                cover_url = img_nodes[0].strip() if img_nodes else ''
                if cover_url.startswith('//'):
                    cover_url = 'http:' + cover_url

                return {
                    'source': 'dangdang',
                    'title': t_str,
                    'author': a_str,
                    'publisher': pub_str,
                    'pubdate': '',
                    'isbn': isbn,
                    'cover_url': cover_url,
                    'description': '',
                    'rating': 9,
                    'tags': []
                }
        except Exception:
            return None
        return None

class UnifiedMetadataProvider:
    """
    统一元数据服务中枢：
    方案二（内置原生 Providers）与 方案三（Calibre 外部插件热插拔）双轨并行。
    优先调度已加载的 Calibre 插件，未命中或未放置插件时自动无缝降级到内置源瀑布流。
    """
    def __init__(self, google_api_key=None, delay=config.REQUEST_DELAY, calibre_plugin_dir=None):
        self.delay = delay
        # 1. 方案二：内置优质纯 Python 数据源
        self.douban = DoubanProvider(delay=delay)
        self.weread = WeReadProvider(delay=delay)
        self.google = GoogleBooksProvider(api_key=google_api_key, delay=delay)
        self.openlibrary = OpenLibraryProvider(delay=delay)
        self.bangumi = BangumiProvider(delay=delay)
        self.dangdang = DangDangProvider(delay=delay)

        # 2. 方案三：Calibre 动态插件加载器
        self.weread.opener = self.douban.opener
        self.google.opener = self.douban.opener
        self.openlibrary.opener = self.douban.opener
        self.bangumi.opener = self.douban.opener
        try:
            self.calibre_loader = calibre_shim.CalibrePluginLoader(plugin_dir=calibre_plugin_dir)
            self.calibre_adapters = self.calibre_loader.load_all()
        except Exception:
            self.calibre_loader = None
            self.calibre_adapters = []

        self.cache = {}
        self.cache_lock = threading.Lock()

    def get_loaded_sources_summary(self):
        """返回当前启用的数据源列表摘要"""
        builtin = ["豆瓣读书", "微信读书", "谷歌图书", "Open Library", "Bangumi 番组计划"]
        external = [f"Calibre插件:{ad.name}" for ad in self.calibre_adapters]
        return {
            'builtin': builtin,
            'external': external,
            'total_external': len(external)
        }

    def fetch_by_isbn(self, isbn):
        if not isbn:
            return None
        clean_isbn = isbn.replace('-', '').strip()
        if clean_isbn in self.cache:
            return self.cache[clean_isbn]

        # [通道 1] 优先调用用户放置的 Calibre 外部插件
        if self.calibre_adapters:
            for ad in self.calibre_adapters:
                meta = ad.identify_by_isbn(clean_isbn)
                if meta and meta.get('title'):
                    meta['_calibre_adapter'] = ad
                    self.cache[clean_isbn] = meta
                    return meta

        # [通道 2] 豆瓣读书 (中文首选)
        sids = self.douban.search(clean_isbn)
        if sids:
            for sid in sids[:3]:
                meta = self.douban.get_subject_details(sid)
                if meta and meta.get('isbn'):
                    self.cache[clean_isbn] = meta
                    return meta

        # [通道 3] Open Library (全球公版与外文原版，免Key秒查)
        ol_meta = self.openlibrary.fetch_by_isbn(clean_isbn)
        if ol_meta and ol_meta.get('title'):
            self.cache[clean_isbn] = ol_meta
            return ol_meta

        # [通道 4] Google Books
        g_results = self.google.search(f"isbn:{clean_isbn}")
        if g_results:
            for g in g_results:
                if g.get('isbn'):
                    self.cache[clean_isbn] = g
                    return g

        return None

    def fetch_by_query(self, query_title, author="", is_collection=False):
        cache_key = f"{query_title}|{author}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        core_title = strip_generic_words(query_title)
        clean_no_parens = re.sub(r'[\(（\[【].*?[\)）\]】]', '', query_title).strip()
        cn_year_title = convert_year_numbers(clean_no_parens)
        clean_author = epub_handler.clean_author_name(author) if author else ""

        queries_to_try = []
        if clean_no_parens:
            queries_to_try.append(clean_no_parens)
        if core_title and core_title != clean_no_parens:
            queries_to_try.append(core_title)
        if cn_year_title and cn_year_title not in queries_to_try:
            queries_to_try.append(cn_year_title)

        if clean_author:
            queries_to_try.append(f"{clean_no_parens} {clean_author}")
            if core_title != clean_no_parens:
                queries_to_try.append(f"{core_title} {clean_author}")

        if query_title not in queries_to_try:
            queries_to_try.append(query_title)

        # [通道 1] 优先调用外部 Calibre 插件
        if self.calibre_adapters:
            for ad in self.calibre_adapters:
                meta = ad.identify_by_query(core_title, author=author)
                if meta and meta.get('title'):
                    if is_title_match(core_title, meta['title'], author_query=author, author_result=meta.get('author', '')) or does_title_correspond(query_title, meta['title'], author, meta.get('author', '')):
                        meta['_calibre_adapter'] = ad
                        self.cache[cache_key] = meta
                        return meta

        # [通道 2] 豆瓣读书 (中文最全)
        for q in queries_to_try:
            sids = self.douban.search(q)
            if sids:
                for sid in sids[:4]:
                    meta = self.douban.get_subject_details(sid)
                    if meta and meta.get('isbn'):
                        if is_title_match(core_title, meta['title'], author_query=author, author_result=meta.get('author', '')) or does_title_correspond(query_title, meta['title'], author, meta.get('author', '')):
                            self.cache[cache_key] = meta
                            return meta

        # [通道 2.5] 当当图书数据库 (国内正版出版物核心源，免Key抗封锁)
        for q in queries_to_try:
            dd_meta = self.dangdang.fetch_by_query(q)
            if dd_meta and dd_meta.get('isbn') and epub_handler.is_valid_isbn(dd_meta['isbn']):
                if is_title_match(core_title, dd_meta['title'], author_query=clean_author, author_result=dd_meta.get('author', '')) or does_title_correspond(query_title, dd_meta['title'], clean_author, dd_meta.get('author', '')):
                    self.cache[cache_key] = dd_meta
                    return dd_meta

        # [通道 3] 微信读书 (中文出版物快速高质补充)
        for q in queries_to_try[:2]:
            wr_list = self.weread.search(q)
            if wr_list:
                for wr in wr_list[:3]:
                    if is_title_match(core_title, wr['title'], author_query=author, author_result=wr.get('author', '')) or does_title_correspond(query_title, wr['title'], author, wr.get('author', '')):
                        self.cache[cache_key] = wr
                        return wr

        # [通道 4] Google Books
        for q in queries_to_try:
            g_results = self.google.search(q)
            if g_results:
                for g in g_results:
                    if g.get('isbn') and (is_title_match(core_title, g['title'], author_query=author, author_result=g.get('author', '')) or does_title_correspond(query_title, g['title'], author_query=author, author_result=g.get('author', ''))):
                        self.cache[cache_key] = g
                        return g

        # [通道 5] Bangumi (轻小说、动漫原作、漫画)
        bgm_meta = self.bangumi.search(core_title)
        if bgm_meta and bgm_meta.get('title'):
            if is_title_match(core_title, bgm_meta['title'], author_query=author, author_result=bgm_meta.get('author', '')) or does_title_correspond(query_title, bgm_meta['title'], author, bgm_meta.get('author', '')):
                self.cache[cache_key] = bgm_meta
                return bgm_meta

        # [通道 6] Open Library
        ol_results = self.openlibrary.search(core_title)
        if ol_results:
            for ol in ol_results:
                if is_title_match(core_title, ol['title'], author_query=author, author_result=ol.get('author', '')):
                    self.cache[cache_key] = ol
                    return ol

        return None

    def download_cover_image(self, meta):
        if not meta:
            return None
        # 1. 外部 Calibre 插件原生下载通道
        adapter = meta.get('_calibre_adapter')
        if adapter:
            im = adapter.download_cover(meta)
            if im:
                return im

        # 2. 网络封面通用自适应下载
        cover_url = meta.get('cover_url')
        if not cover_url:
            return None
        return download_cover_from_url(cover_url, delay=self.delay)
