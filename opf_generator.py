# -*- coding: utf-8 -*-
"""
OPF and Metadata JSON Generator for Book Organizer
Produces standard Calibre-compatible OPF and metadata.json files
matching the target library structure.
"""
import os
import json
import uuid
import datetime
import xml.sax.saxutils as saxutils

import config

def escape_xml(s):
    if not s:
        return ""
    return saxutils.escape(str(s))

def generate_metadata_json(meta, out_path, **kwargs):
    pubdate_iso = config.format_iso_datetime(meta.get('pubdate', ''))
    data = {
        "title": meta.get('title', ''),
        "creator": meta.get('author', ''),
        "isbn": meta.get('isbn', ''),
        "publisher": meta.get('publisher', ''),
        "pubdate": pubdate_iso,
        "language": meta.get('language', 'zho'),
        "description": meta.get('description', '')
    }
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def generate_calibre_opf(meta, out_path, cover_filename="cover.jpg", calibre_id=1, book_filename=None, **kwargs):
    pubdate_iso = config.format_iso_datetime(meta.get('pubdate', ''))
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    unique_uuid = str(uuid.uuid4())

    title = meta.get('title', '')
    author = meta.get('author', '')
    publisher = meta.get('publisher', '')
    isbn = meta.get('isbn', '')
    description = meta.get('description', '')
    rating = str(meta.get('rating', 8))
    language = meta.get('language', 'zho')

    # 标签/分类
    tags = meta.get('tags', [])
    tags_xml = "\n".join([f"        <dc:subject>{escape_xml(t)}</dc:subject>" for t in tags])
    if tags_xml:
        tags_xml += "\n"

    # 外部标识符
    douban_id = meta.get('douban_id')
    douban_xml = f'        <dc:identifier opf:scheme="NEW_DOUBAN">{escape_xml(douban_id)}</dc:identifier>\n' if douban_id else ''

    google_id = meta.get('google_id')
    google_xml = f'        <dc:identifier opf:scheme="GOOGLE">{escape_xml(google_id)}</dc:identifier>\n' if google_id else ''

    edition_metadata = '&quot;table&quot;: &quot;custom_column_3&quot;, &quot;column&quot;: &quot;value&quot;, &quot;datatype&quot;: &quot;text&quot;, &quot;is_multiple&quot;: null, &quot;kind&quot;: &quot;field&quot;, &quot;name&quot;: &quot;版本信息&quot;, &quot;search_terms&quot;: [&quot;#edition&quot;], &quot;label&quot;: &quot;edition&quot;, &quot;colnum&quot;: 3, &quot;display&quot;: {&quot;use_decorations&quot;: false, &quot;description&quot;: &quot;&quot;, &quot;web_search_template&quot;: &quot;&quot;}, &quot;is_custom&quot;: true, &quot;is_category&quot;: true, &quot;link_column&quot;: &quot;value&quot;, &quot;category_sort&quot;: &quot;value&quot;, &quot;is_csp&quot;: false, &quot;is_editable&quot;: true, &quot;rec_index&quot;: 22, &quot;#value#&quot;: null, &quot;#extra#&quot;: null, &quot;is_multiple2&quot;: {}'
    language_label_metadata = '&quot;table&quot;: &quot;custom_column_2&quot;, &quot;column&quot;: &quot;value&quot;, &quot;datatype&quot;: &quot;text&quot;, &quot;is_multiple&quot;: null, &quot;kind&quot;: &quot;field&quot;, &quot;name&quot;: &quot;显示语言&quot;, &quot;search_terms&quot;: [&quot;#language_label&quot;], &quot;label&quot;: &quot;language_label&quot;, &quot;colnum&quot;: 2, &quot;display&quot;: {&quot;use_decorations&quot;: false, &quot;description&quot;: &quot;&quot;, &quot;web_search_template&quot;: &quot;&quot;}, &quot;is_custom&quot;: true, &quot;is_category&quot;: true, &quot;link_column&quot;: &quot;value&quot;, &quot;category_sort&quot;: &quot;value&quot;, &quot;is_csp&quot;: false, &quot;is_editable&quot;: true, &quot;rec_index&quot;: 23, &quot;#value#&quot;: null, &quot;#extra#&quot;: null, &quot;is_multiple2&quot;: {}'
    translator_metadata = '&quot;table&quot;: &quot;custom_column_1&quot;, &quot;column&quot;: &quot;value&quot;, &quot;datatype&quot;: &quot;text&quot;, &quot;is_multiple&quot;: null, &quot;kind&quot;: &quot;field&quot;, &quot;name&quot;: &quot;译者&quot;, &quot;search_terms&quot;: [&quot;#translator&quot;], &quot;label&quot;: &quot;translator&quot;, &quot;colnum&quot;: 1, &quot;display&quot;: {&quot;use_decorations&quot;: true, &quot;description&quot;: &quot;&quot;, &quot;web_search_template&quot;: &quot;&quot;}, &quot;is_custom&quot;: true, &quot;is_category&quot;: true, &quot;link_column&quot;: &quot;value&quot;, &quot;category_sort&quot;: &quot;value&quot;, &quot;is_csp&quot;: false, &quot;is_editable&quot;: true, &quot;rec_index&quot;: 24, &quot;#value#&quot;: null, &quot;#extra#&quot;: null, &quot;is_multiple2&quot;: {}'

    opf_content = f"""<?xml version='1.0' encoding='utf-8'?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="uuid_id" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:identifier opf:scheme="calibre" id="calibre_id">{calibre_id}</dc:identifier>
        <dc:identifier opf:scheme="uuid" id="uuid_id">{unique_uuid}</dc:identifier>
        <dc:title>{escape_xml(title)}</dc:title>
        <dc:creator opf:file-as="{escape_xml(author)}" opf:role="aut">{escape_xml(author)}</dc:creator>
        <dc:contributor opf:file-as="calibre" opf:role="bkp">calibre (8.5.0) [https://calibre-ebook.com]</dc:contributor>
        <dc:date>{pubdate_iso}</dc:date>
        <dc:description>{escape_xml(description)}</dc:description>
        <dc:publisher>{escape_xml(publisher)}</dc:publisher>
        <dc:identifier opf:scheme="ISBN">{escape_xml(isbn)}</dc:identifier>
{douban_xml}{google_xml}        <dc:language>{escape_xml(language)}</dc:language>
{tags_xml}        <meta name="calibre:rating" content="{rating}"/>
        <meta name="calibre:timestamp" content="{now_iso}"/>
        <meta name="calibre:title_sort" content="{escape_xml(title)}"/>
        <meta name="calibre:user_metadata:#edition" content="{{{edition_metadata}}}"/>
        <meta name="calibre:user_metadata:#language_label" content="{{{language_label_metadata}}}"/>
        <meta name="calibre:user_metadata:#translator" content="{{{translator_metadata}}}"/>
    </metadata>
    <guide>
        <reference type="cover" title="封面" href="{escape_xml(cover_filename)}"/>
    </guide>
</package>
"""
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(opf_content)
