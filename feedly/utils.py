# MIT License
#
# Copyright (c) 2020 Tony Wu <tony[dot]wu(at)nyu[dot]edu>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

from __future__ import annotations

import logging
import string
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from hashlib import sha1
from typing import Any, Dict, List, Union
from urllib.parse import urlsplit

import simplejson as json
from scrapy.http import Request, TextResponse

from .datastructures import KeywordCollection, KeywordStore
from .urlkit import domain_parents, ensure_protocol, is_absolute_http

JSONType = Union[str, bool, int, float, None, List['JSONType'], Dict[str, 'JSONType']]
JSONDict = Dict[str, JSONType]
SpiderOutput = List[Union[JSONDict, Request]]

log = logging.getLogger('feedly.utils')


def parse_html(domstring, url='about:blank') -> TextResponse:
    return TextResponse(url=url, body=domstring, encoding='utf8')


def json_converters(value: Any) -> JSONType:
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(type(value))


def load_jsonlines(file) -> List[JSONDict]:
    return [json.loads(line) for line in file.read().split('\n') if line]


def datetime_converters(dt: Union[str, int, float, datetime], tz=timezone.utc) -> datetime:
    if isinstance(dt, datetime):
        return dt
    if isinstance(dt, str):
        return datetime.fromisoformat(dt)
    if isinstance(dt, (int, float)):
        try:
            return datetime.fromtimestamp(dt, tz=tz)
        except ValueError:
            return datetime.fromtimestamp(dt / 1000, tz=tz)
    raise TypeError('dt must be of type str, int, float, or datetime')


def sha1sum(s: Union[str, bytes]) -> str:
    if isinstance(s, str):
        s = s.encode()
    return sha1(s).hexdigest()


def ensure_collection(supplier):
    def converter(obj):
        if obj is None:
            return supplier()
        return supplier(obj)
    return converter


def falsy(v):
    return v in {0, None, False, '0', 'None', 'none', 'False', 'false', 'null', 'undefined', 'NaN'}


def wait(t):
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < t:
        time.sleep(0.1)


@contextmanager
def watch_for_timing(name, limit):
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        if duration > limit:
            logging.getLogger('profiler.timing').warn(f'[Timing violation] {name} took {duration * 1000:.0f}ms; desired time is {limit * 1000:.0f}ms.')


def guard_json(text: str) -> JSONDict:
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        log.error(e)
        return {}


PATH_UNSAFE = ''.join(set(string.punctuation + ' ') - set('-_/.'))


def aggressive_replace_chars(s, encoding='latin_1'):
    return s.encode(encoding, 'replace').decode(encoding, 'ignore')


def replace_unsafe_chars(s, repl='-', chars=PATH_UNSAFE):
    for c in chars:
        if c in s:
            s = s.replace(c, repl)
    return s


def pathsafe(s):
    return replace_unsafe_chars(aggressive_replace_chars(s))


SIMPLEJSON_KWARGS = {
    'ensure_ascii': True,
    'default': json_converters,
    'for_json': True,
    'iterable_as_array': True,
}


class HyperlinkStore(KeywordStore):
    TARGET_ATTRS = {'src', 'href', 'data-src', 'data-href'}

    def __init__(self, serialized: JSONDict = None):
        super().__init__()
        self._index: Dict[int, str]
        if serialized:
            self._deserialize(serialized)

    def _deserialize(self, dict_: JSONDict):
        for k, v in dict_.items():
            hash_ = hash(k)
            self._index[hash_] = k
            self._taggings[hash_] = {c: set(ls) for c, ls in v.items()}

    def parse_html(self, source, markup, **kwargs):
        markup = parse_html(markup)
        for attrib in self.TARGET_ATTRS:
            elements = markup.css(f'[{attrib}]')
            for tag in elements:
                url = tag.attrib.get(attrib)
                if not is_absolute_http(url):
                    continue
                url = ensure_protocol(url)

                keywords: KeywordCollection = {
                    'source': {source},
                    'domain': set(domain_parents(urlsplit(url).netloc)),
                    'tag': set(),
                }
                keywords['tag'].add(tag.xpath('name()').get())
                self.put(url, **keywords, **kwargs)
