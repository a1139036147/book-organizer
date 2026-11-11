# -*- coding: utf-8 -*-
from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata

class MockCalibrePlugin(Source):
    name = 'Mock Calibre Plugin'
    description = 'Test plugin'
    author = 'Test'
    version = (1, 0, 0)
    capabilities = frozenset(['identify', 'cover'])

    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        isbn = identifiers.get('isbn')
        if isbn == '9787532169481':
            mi = Metadata('草婴译著全集', ['草婴', '列夫·托尔斯泰'])
            mi.set_identifier('isbn', '9787532169481')
            mi.publisher = '上海文艺出版社'
            mi.pubdate = '2019-01-01'
            mi.comments = '草婴先生毕生翻译之托尔斯泰巨著全集。'
            mi.tags = ['文学', '名著', '托尔斯泰']
            result_queue.put(mi)
        elif title and '草婴' in title:
            mi = Metadata('草婴译著全集', ['草婴'])
            mi.set_identifier('isbn', '9787532169481')
            result_queue.put(mi)
