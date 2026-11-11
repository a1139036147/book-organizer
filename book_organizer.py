# -*- coding: utf-8 -*-
"""
Book Organizer - 智能图书整理工具
将未整理的电子书按标准结构整理：
{书名}（{作者}）{isbn-{ISBN}}
├── cover.jpg
├── metadata.json
├── {书名}-{作者}.{ext}
└── {书名}-{作者}.opf

元数据支持豆瓣、谷歌图书多源解析，深入书内提取出版ISBN；
书内多ISBN将联网验证，拥有合集/分卷出版ISBN的正规出版物（如《草婴译著全集》）正常入库；
若均为互不相关的单本且无合集ISBN则判为拼凑合集跳过。
"""
import os
import sys
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

import shutil
import argparse
import datetime
from PIL import Image, ImageDraw, ImageFont

# 确保在 Windows 控制台或管道下输出不会因编码报错
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import config
import metadata_provider
import epub_handler
import opf_generator

def create_default_cover(title, author, out_path, size=(600, 800)):
    """在无网络封面且无内嵌封面时，自动生成一张基础封面图片"""
    im = Image.new('RGB', size, color=(52, 73, 94))
    draw = ImageDraw.Draw(im)
    margin = 30
    draw.rectangle([margin, margin, size[0] - margin, size[1] - margin], outline=(236, 240, 241), width=4)
    try:
        font_title = ImageFont.truetype("msyh.ttc", 36)
        font_author = ImageFont.truetype("msyh.ttc", 24)
    except Exception:
        font_title = ImageFont.load_default()
        font_author = ImageFont.load_default()
    
    disp_title = title[:20] if len(title) > 20 else title
    disp_author = author[:20] if len(author) > 20 else author
    draw.text((size[0]//2, size[1]//3), disp_title, fill=(255, 255, 255), anchor="mm", font=font_title)
    draw.text((size[0]//2, size[1]//2), disp_author, fill=(200, 200, 200), anchor="mm", font=font_author)
    im.save(out_path, 'JPEG', quality=90)

class OrganizerReporter:
    def __init__(self, msg_queue=None):
        self.msg_queue = msg_queue

    def log(self, message, level='info'):
        if self.msg_queue:
            self.msg_queue.put({'type': 'log', 'text': message, 'tag': level})

    def progress(self, current, total, filename=''):
        if self.msg_queue:
            self.msg_queue.put({'type': 'progress', 'current': current, 'total': total, 'filename': filename})

    def stats(self, stats_dict):
        if self.msg_queue:
            self.msg_queue.put({
                'type': 'stats',
                'data': {
                    'total': stats_dict.get('total_scanned', 0),
                    'organized': len(stats_dict.get('organized', [])),
                    'col_skip': len(stats_dict.get('skipped_collections', [])),
                    'no_isbn': len(stats_dict.get('skipped_no_isbn', [])),
                    'error': len(stats_dict.get('errors', []))
                }
            })

class BookOrganizer:
    def __init__(self, src_dir, dst_dir, action='copy', google_api_key=None, delay=config.REQUEST_DELAY,
                 skip_collections=True, dry_run=False, log_callback=None, progress_callback=None,
                 stats_callback=None, stop_event=None, reporter=None, request_delay=None, threads=4):
        if request_delay is not None:
            delay = request_delay
        if reporter is not None:
            log_callback = reporter.log
            progress_callback = reporter.progress
            stats_callback = reporter.stats
        self.src_dir = os.path.abspath(src_dir)
        self.dst_dir = os.path.abspath(dst_dir)
        self.action = action  # 'copy' or 'move'
        self.skip_collections = skip_collections
        self.dry_run = dry_run
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.stats_callback = stats_callback
        self.stop_event = stop_event
        self.provider = metadata_provider.UnifiedMetadataProvider(google_api_key=google_api_key, delay=delay)

        self.threads = max(2, min(20, int(threads or 4)))
        self.lock = threading.Lock()
        self.processed_counter = 0

        self.stats = {
            'total_scanned': 0,
            'organized': [],
            'skipped_collections': [],
            'skipped_no_isbn': [],
            'errors': []
        }

    def log(self, message, level='info'):
        print(message)
        if self.log_callback:
            try:
                self.log_callback(message, level)
            except Exception:
                pass

    def notify_stats(self):
        if self.stats_callback:
            try:
                with self.lock: st = {'total_scanned': self.stats['total_scanned'], 'organized': list(self.stats['organized']), 'skipped_collections': list(self.stats['skipped_collections']), 'skipped_no_isbn': list(self.stats['skipped_no_isbn']), 'errors': list(self.stats['errors'])}; self.stats_callback(st)
            except Exception:
                pass

    def get_summary_text(self):
        org = len(self.stats.get('organized', []))
        col = len(self.stats.get('skipped_collections', []))
        no_isbn = len(self.stats.get('skipped_no_isbn', []))
        err = len(self.stats.get('errors', []))
        tot = self.stats.get('total_scanned', 0)
        mode = "预演分析完成" if self.dry_run else "整理入库完成"
        return (
            f"【{mode}】\n"
            f"待处理扫描总数: {tot} 本\n"
            f"成功整理入库: {org} 本\n"
            f"跳过无ISBN合集: {col} 本\n"
            f"跳过无出版ISBN: {no_isbn} 本\n"
            f"发生处理异常: {err} 本"
        )

    def run(self, limit=None, dry_run=None):
        if dry_run is not None:
            self.dry_run = dry_run
        self.log("=" * 65, 'heading')
        self.log("[智能图书整理工具启动]", 'heading')
        self.log(f"源文件夹:       {self.src_dir}", 'info')
        self.log(f"目标书库:       {self.dst_dir}", 'info')
        mode_desc = '[预演模式/DRY-RUN]' if self.dry_run else ('复制文件 (保留源文件)' if self.action == 'copy' else '移动文件')
        self.log(f"操作模式:       {mode_desc}", 'info')
        self.log(f"合集策略:       书内多ISBN联网验证，正规全集/套装正常入库；无独立出版ISBN拼凑合集跳过", 'info')
        summary = self.provider.get_loaded_sources_summary()
        ext_count = summary.get("total_external", 0)
        ext_desc = f"已加载 {ext_count} 个外部插件 ({', '.join(summary['external'])})" if ext_count > 0 else "未放置外部插件 (已就绪热插拔)"
        self.log(f"元数据引擎:     双轨架构 [内置: 豆瓣/微信读书/谷歌图书/OpenLibrary/Bangumi] + [Calibre插件: {ext_desc}]", "info")
        self.log("=" * 65, 'heading')

        if not os.path.exists(self.src_dir):
            self.log(f"错误: 源目录不存在: {self.src_dir}", 'error')
            return self.stats

        if not self.dry_run and not os.path.exists(self.dst_dir):
            os.makedirs(self.dst_dir, exist_ok=True)

        files = sorted(os.listdir(self.src_dir))
        book_files = [f for f in files if f.lower().endswith(config.SUPPORTED_EXTENSIONS)]
        self.stats['total_scanned'] = len(book_files)
        self.notify_stats()
        self.log(f"在源目录下发现 {len(book_files)} 个受支持的电子书文件。", 'info')

        if limit and limit > 0:
            book_files = book_files[:limit]
            self.log(f"已设置处理数量限制: 前 {limit} 本图书。", 'info')

        total_files = len(book_files)
        self.processed_counter = 0
        self.log(f"并发模式:       启动 {self.threads} 个工作线程并发处理 (范围2-20)", "info")
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def worker_task(item):
            file_path, filename, ext = item
            if self.stop_event and self.stop_event.is_set(): return
            with self.lock:
                self.processed_counter += 1
                curr_idx = self.processed_counter

            self.log(f"[{curr_idx:03d}/{total_files:03d}] 正在分析: {filename}", "heading")
            if self.progress_callback:
                try: self.progress_callback(curr_idx, total_files, filename)
                except Exception: pass

            try:
                self.process_single_book(file_path, filename, ext)
            except Exception as e:
                err_msg = f"处理异常: {str(e)}"
                self.log(f"  [错误] {err_msg}", "error")
                with self.lock: self.stats["errors"].append((filename, err_msg))
                self.notify_stats()

            self.log("", "info")

        task_items = [(os.path.join(self.src_dir, fn), fn, os.path.splitext(fn)[1].lower()) for fn in book_files]
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = [executor.submit(worker_task, item) for item in task_items]
            for f in as_completed(futures):
                if self.stop_event and self.stop_event.is_set():
                    executor.shutdown(wait=False, cancel_futures=True)
                    self.log("[提示] 任务已被用户手动终止，正在退出工作线程...", "warning")
                    break

        self.print_summary()
        return self.stats

    def process_single_book(self, file_path, filename, ext):
        if self.stop_event and self.stop_event.is_set():
            return

        # 1. 深入书内全文检索出版ISBN（版权页、OPF、正文等）与基础元数据
        internal_isbns = epub_handler.scan_isbns_from_file(file_path)
        epub_meta = epub_handler.extract_epub_metadata(file_path) if ext == '.epub' else {
            'title': '', 'creator': '', 'isbn': '', 'publisher': '', 'pubdate': '', 'description': '', 'cover_image': None
        }

        # 2. 提取清洗后的检索书名、作者提示、合集特征
        cleaned_search_title = epub_handler.clean_title_for_search(filename, epub_meta.get('title', ''))
        author_hint = epub_meta.get('creator', '')
        is_col_name, col_kw_reason = epub_handler.check_is_collection(filename, epub_meta.get('title', ''))

        meta = None

        # 3. 核心决策流水线
        # 场景 A: 书内扫描到多个不同的出版ISBN（正规全集/套装，或者多书拼凑合集）
        if len(internal_isbns) > 1:
            self.log(f"  -> 书内扫描到 {len(internal_isbns)} 个出版ISBN，启动联网验证（验证是否为拥有合集/分卷出版ISBN的正规全集/套装，或拼凑合集）...", 'info')

            collection_isbn_meta = None
            volume_isbn_meta = None

            # 3.1 优先通过清洗后的书名与作者联网检索：验证是否存在官方合集/套装出版记录
            q_meta = self.provider.fetch_by_query(cleaned_search_title, author=author_hint, is_collection=True)
            if q_meta and q_meta.get('isbn') and epub_handler.is_valid_isbn(q_meta['isbn']):
                if metadata_provider.is_collection_title_match(cleaned_search_title, q_meta.get('title')):
                    collection_isbn_meta = q_meta
                    self.log(f"  -> 成功匹配到官方合集/套装出版记录: 《{q_meta['title']}》 (ISBN: {q_meta['isbn']}, 来源: {q_meta.get('source')})", 'info')

            # 3.2 联网验证书内提取出来的各个候选 ISBN
            for candidate_isbn in sorted(internal_isbns)[:6]:
                c_meta = self.provider.fetch_by_isbn(candidate_isbn)
                if c_meta and c_meta.get('isbn'):
                    c_title = c_meta.get('title', '')
                    # 检查该 ISBN 是否是整个合集的出版 ISBN
                    if metadata_provider.is_collection_title_match(cleaned_search_title, c_title):
                        if not collection_isbn_meta:
                            collection_isbn_meta = c_meta
                            self.log(f"  -> 书内 ISBN {candidate_isbn} 验证为合集官方ISBN: 《{c_title}》", 'info')
                        else:
                            self.log(f"  -> 书内 ISBN {candidate_isbn} 验证对应本书: 《{c_title}》", 'info')
                    # 检查该 ISBN 是否对应本书的某一分卷（如《草婴译著全集·第一卷》或《半泽直树 1》）
                    elif metadata_provider.does_title_correspond(cleaned_search_title, c_title, author_hint, c_meta.get('author', '')):
                        if not volume_isbn_meta:
                            volume_isbn_meta = c_meta
                        self.log(f"  -> 书内 ISBN {candidate_isbn} 对应本书分卷: 《{c_title}》 (作者: {c_meta.get('author', '未知')})", 'info')

            # 3.3 评估验证结果
            if collection_isbn_meta:
                meta = collection_isbn_meta
                self.log(f"  -> [合集识别成功] 采纳合集出版ISBN: {meta['isbn']} (《{meta['title']}》)", 'info')
            elif volume_isbn_meta:
                meta = volume_isbn_meta
                self.log(f"  -> [合集分卷识别成功] 采纳本书分卷出版ISBN: {meta['isbn']} (《{meta['title']}》)", 'info')
            else:
                # 书内各个 ISBN 经联网验证均与当前书名无关，且网上无合集出版条目
                col_reason = f"书内包含 {len(internal_isbns)} 个ISBN，经网络验证均不对应当前书名，属于无独立ISBN的拼凑合集"
                self.log(f"  * [跳过不整理] 判定为多书拼凑合集，本身无出版ISBN号 ({col_reason})。", 'skip')
                with self.lock: self.stats['skipped_collections'].append((filename, col_reason))
                self.notify_stats()
                return

        # 场景 B: 书内恰好扫描到 1 个出版 ISBN
        elif len(internal_isbns) == 1 or epub_meta.get('isbn'):
            single_internal_isbn = list(internal_isbns)[0] if len(internal_isbns) == 1 else epub_meta.get('isbn')
            self.log(f"  -> 书内发现唯一出版ISBN: {single_internal_isbn}，正在联网查询元数据...", 'info')
            meta = self.provider.fetch_by_isbn(single_internal_isbn)
            if meta and not metadata_provider.does_title_correspond(cleaned_search_title, meta.get('title', ''), author_hint, meta.get('author', '')):
                self.log(f"  -> 提示: 书内ISBN对应《{meta.get('title')}》与当前书名存在差异，尝试书名检索校验...", 'warning')
                q_meta = self.provider.fetch_by_query(cleaned_search_title, author=author_hint, is_collection=is_col_name)
                if q_meta and metadata_provider.does_title_correspond(cleaned_search_title, q_meta.get('title', ''), author_hint, q_meta.get('author', '')):
                    meta = q_meta

            if not meta:
                q_meta = self.provider.fetch_by_query(cleaned_search_title, author=author_hint, is_collection=is_col_name)
                if q_meta and q_meta.get('isbn') and epub_handler.is_valid_isbn(q_meta['isbn']):
                    meta = q_meta
                else:
                    self.log("  -> 网络暂未收录最新记录，使用书内元数据与唯一ISBN补充构建...", 'info')
                    meta = {
                        'source': 'internal',
                        'douban_id': None,
                        'google_id': None,
                        'title': epub_meta['title'] or epub_handler.clean_title_for_search(filename, ''),
                        'author': epub_meta['creator'] or '未知',
                        'publisher': epub_meta['publisher'] or '未知出版社',
                        'pubdate': epub_meta['pubdate'] or '',
                        'isbn': single_internal_isbn,
                        'cover_url': '',
                        'description': epub_meta['description'] or '',
                        'rating': 8,
                        'tags': []
                    }

        # 场景 C: 书内未提取到任何出版 ISBN (0 个)
        else:
            self.log(f"  -> 书内未直接提取到出版ISBN，联网检索元数据 (书名: '{cleaned_search_title}', 作者: '{author_hint}')...", 'info')
            meta = self.provider.fetch_by_query(cleaned_search_title, author=author_hint, is_collection=is_col_name)

        # 4. 核心终检：是否有合法的出版 ISBN
        has_isbn = bool(meta and meta.get('isbn') and epub_handler.is_valid_isbn(meta['isbn']))

        # 如果被判定为合集特征，但最终无法获得合法出版ISBN -> 跳过！
        if is_col_name and not has_isbn:
            self.log(f"  * [跳过不整理] 疑似多本书合集/全本 ({col_kw_reason})，且未查询到出版ISBN号。", 'skip')
            with self.lock: self.stats['skipped_collections'].append((filename, col_kw_reason))
            self.notify_stats()
            return

        # 如果单本书也完全未能查询到有效出版ISBN号 -> 跳过！
        if not has_isbn:
            self.log("  * [跳过不整理] 未能从书内或网络获取到有效出版ISBN号，跳过整理。", 'skip')
            with self.lock: self.stats['skipped_no_isbn'].append((filename, "未找到有效ISBN号"))
            self.notify_stats()
            return

        # 5. 校验通过，进入标准组织入库流程
        safe_title = config.sanitize_filename(meta['title'])
        safe_author = config.sanitize_filename(meta.get('author', ''))
        if not safe_author or safe_author == '未知':
            if author_hint:
                safe_author = author_hint
            else:
                safe_author = '未知'
        if len(safe_title) > 40:
            safe_title = safe_title[:40].strip(' -_')
        if len(safe_author) > 18:
            safe_author = safe_author[:18].strip(' -_')
        clean_isbn = meta['isbn'].replace('-', '').strip()

        folder_name = f"{safe_title}（{safe_author}）{{isbn-{clean_isbn}}}"
        target_dir = os.path.join(self.dst_dir, folder_name)

        target_book_filename = f"{safe_title}-{safe_author}{ext}"
        target_book_path = os.path.join(target_dir, target_book_filename)
        target_opf_path = os.path.join(target_dir, f"{safe_title}-{safe_author}.opf")
        target_json_path = os.path.join(target_dir, 'metadata.json')
        target_cover_path = os.path.join(target_dir, 'cover.jpg')

        if self.dry_run:
            self.log(f"  [成功匹配] (ISBN: {clean_isbn}, 来源: {meta.get('source')})", 'success')
            self.log(f"    拟生成目录: {folder_name}", 'info')
            self.log(f"    拟存放文件: {target_book_filename}, metadata.json, {safe_title}-{safe_author}.opf, cover.jpg", 'info')
            with self.lock: self.stats['organized'].append((filename, folder_name, clean_isbn))
            self.notify_stats()
            return

        os.makedirs(target_dir, exist_ok=True)

        if self.action == 'move':
            if os.path.exists(target_book_path):
                try:
                    os.chmod(target_book_path, 0o777)
                    os.remove(target_book_path)
                except Exception:
                    pass
            try:
                shutil.move(file_path, target_book_path)
            except Exception:
                shutil.copyfile(file_path, target_book_path)
                try: os.remove(file_path)
                except Exception: pass
        else:
            if os.path.exists(target_book_path):
                try:
                    os.chmod(target_book_path, 0o777)
                except Exception:
                    pass
            try:
                shutil.copyfile(file_path, target_book_path)
            except Exception as copy_err:
                try:
                    shutil.copy2(file_path, target_book_path)
                except Exception:
                    raise copy_err

        # 5.2 处理封面 cover.jpg
        cover_saved = False
        if meta.get('cover_url'):
            net_cover = self.provider.download_cover_image(meta)
            if net_cover:
                net_cover.save(target_cover_path, 'JPEG', quality=95)
                cover_saved = True

        if not cover_saved and epub_meta.get('cover_image'):
            epub_meta['cover_image'].save(target_cover_path, 'JPEG', quality=95)
            cover_saved = True

        if not cover_saved:
            create_default_cover(meta['title'], meta['author'], target_cover_path)

        # 5.3 生成 metadata.json
        opf_generator.generate_metadata_json(meta, target_json_path)

        # 5.4 生成 .opf 元数据文件
        opf_generator.generate_calibre_opf(meta, target_opf_path, book_filename=target_book_filename)

        self.log(f"  [整理完成] 已成功规范化入库: {folder_name}", 'success')
        with self.lock: self.stats['organized'].append((filename, folder_name, clean_isbn))
        self.notify_stats()

    def print_summary(self):
        self.log("=" * 65, 'heading')
        self.log("[图书整理汇总统计报告]", 'heading')
        self.log(f"扫描文件总数:       {self.stats['total_scanned']}", 'info')
        self.log(f"成功整理入库:       {len(self.stats['organized'])} 本", 'success')
        self.log(f"跳过多书合集:       {len(self.stats['skipped_collections'])} 本", 'warning')
        self.log(f"跳过无ISBN图书:     {len(self.stats['skipped_no_isbn'])} 本", 'warning')
        self.log(f"处理发生错误:       {len(self.stats['errors'])} 本", 'error' if self.stats['errors'] else 'info')
        self.log("=" * 65, 'heading')

        if self.stats['organized']:
            self.log("[整理入库清单]:", 'success')
            for item in self.stats['organized']:
                if len(item) == 3:
                    fn, fld, isbn = item
                    self.log(f"  + {fld}", 'info')
                else:
                    self.log(f"  + {item[0]} -> {item[1]}", 'info')

        if self.stats['skipped_collections']:
            self.log("[跳过多书合集清单]:", 'warning')
            for fn, reason in self.stats['skipped_collections']:
                self.log(f"  - {fn} ({reason})", 'info')

        if self.stats['skipped_no_isbn']:
            self.log("[跳过无ISBN图书清单]:", 'warning')
            for fn, reason in self.stats['skipped_no_isbn']:
                self.log(f"  - {fn} ({reason})", 'info')

def main():
    parser = argparse.ArgumentParser(description="智能图书整理工具 - 规范化整理入库")
    parser.add_argument('--src', default=config.DEFAULT_SRC_DIR, help="未整理电子书目录")
    parser.add_argument('--dst', default=config.DEFAULT_DST_DIR, help="目标规范书库目录")
    parser.add_argument('--action', choices=['copy', 'move'], default='copy', help="文件操作: copy 或 move")
    parser.add_argument('--google-key', default=None, help="Google Books API Key")
    parser.add_argument('--delay', type=float, default=config.REQUEST_DELAY, help="网络请求间隔(秒)")
    parser.add_argument('--no-skip-col', action='store_true', help="不跳过多书合集")
    parser.add_argument('--dry-run', action='store_true', help="仅预演分析，不写入磁盘")
    parser.add_argument('--limit', type=int, default=None, help="仅处理前N本书")

    args = parser.parse_args()

    organizer = BookOrganizer(
        src_dir=args.src,
        dst_dir=args.dst,
        action=args.action,
        google_api_key=args.google_key,
        delay=args.delay,
        skip_collections=not args.no_skip_col,
        dry_run=args.dry_run
    )
    organizer.run(limit=args.limit)

if __name__ == '__main__':
    main()




