# -*- coding: utf-8 -*-
from calibre.ebooks.metadata.sources.base import Source
from calibre.ebooks.metadata.book.base import Metadata

class GoodreadsMock(Source):
    name = 'Goodreads Community'
    def identify(self, log, result_queue, abort, title=None, authors=None, identifiers={}, timeout=30):
        isbn = identifiers.get('isbn')
        if isbn == '9781234567890':
            mi = Metadata('The Great Novel', ['F. Scott'])
            mi.set_identifier('isbn', '9781234567890')
            mi.publisher = 'Scribner'
            result_queue.put(mi)
