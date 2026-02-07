# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
"""Native HTML link extractor - Cython implementation.

Прискорення 3-5x для витягування посилань.

Build:
    cythonize -i html_parser.pyx
"""

import re
from typing import List, Set
from urllib.parse import urljoin

# Precompiled regex for href extraction
cdef object HREF_PATTERN = re.compile(
    rb'<a[^>]+href=["\']([^"\'>]+)["\']',
    re.IGNORECASE
)

cdef object SRC_PATTERN = re.compile(
    rb'<(?:img|script|link)[^>]+(?:src|href)=["\']([^"\'>]+)["\']',
    re.IGNORECASE
)


cdef str _get_domain_inline(str url):
    """Inline domain extraction."""
    cdef Py_ssize_t start
    cdef Py_ssize_t end
    
    if url is None:
        return None
    
    if url[:7] == 'http://':
        start = 7
    elif url[:8] == 'https://':
        start = 8
    else:
        return None
    
    end = len(url)
    
    cdef Py_ssize_t slash_pos = url.find('/', start)
    cdef Py_ssize_t query_pos = url.find('?', start)
    cdef Py_ssize_t hash_pos = url.find('#', start)
    
    if slash_pos != -1 and slash_pos < end:
        end = slash_pos
    if query_pos != -1 and query_pos < end:
        end = query_pos
    if hash_pos != -1 and hash_pos < end:
        end = hash_pos
    
    if start >= end:
        return None
    
    return url[start:end]


cdef str _make_absolute_inline(str base_url, str relative_url):
    """Inline make absolute URL."""
    cdef str domain
    
    if relative_url is None or len(relative_url) == 0:
        return base_url
    
    # Вже абсолютний
    if relative_url[:7] == 'http://' or relative_url[:8] == 'https://':
        return relative_url
    
    # Protocol-relative
    if relative_url[:2] == '//':
        if base_url[:5] == 'https':
            return 'https:' + relative_url
        return 'http:' + relative_url
    
    # Абсолютний шлях
    if relative_url[0] == '/':
        domain = _get_domain_inline(base_url)
        if domain is None:
            return relative_url
        
        if base_url[:5] == 'https':
            return 'https://' + domain + relative_url
        return 'http://' + domain + relative_url
    
    # Відносний шлях - потрібен повний urljoin
    return urljoin(base_url, relative_url)


cpdef list parse_links_fast(str html, str base_url=None):
    """
    Швидке витягування посилань з HTML.
    
    Використовує regex замість DOM parsing для швидкості.
    3-5x швидше за BeautifulSoup для простих випадків.
    
    Args:
        html: HTML контент
        base_url: Базовий URL для перетворення відносних посилань
        
    Returns:
        Список URL посилань
    """
    if html is None or len(html) == 0:
        return []
    
    cdef bytes html_bytes = html.encode('utf-8', errors='ignore')
    cdef list matches = HREF_PATTERN.findall(html_bytes)
    cdef set seen = set()
    cdef list result = []
    cdef bytes match
    cdef str url
    
    for match in matches:
        try:
            url = match.decode('utf-8', errors='ignore')
        except:
            continue
        
        # Skip special links
        if url.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
            continue
        
        # Deduplicate
        if url in seen:
            continue
        seen.add(url)
        
        # Make absolute if base_url provided
        if base_url is not None and not url.startswith(('http://', 'https://')):
            # Використовуємо inline make_absolute замість імпорту
            url = _make_absolute_inline(base_url, url)
        
        result.append(url)
    
    return result


cpdef list parse_all_urls_fast(str html):
    """
    Витягує ВСІ URL з HTML (href, src, тощо).
    
    Швидша версія для повного сканування.
    
    Args:
        html: HTML контент
        
    Returns:
        Список всіх URL
    """
    if html is None:
        return []
    
    cdef bytes html_bytes = html.encode('utf-8', errors='ignore')
    cdef set seen = set()
    cdef list result = []
    cdef bytes match
    cdef str url
    
    # Extract hrefs
    for match in HREF_PATTERN.findall(html_bytes):
        try:
            url = match.decode('utf-8', errors='ignore')
            if url not in seen:
                seen.add(url)
                result.append(url)
        except:
            pass
    
    # Extract src
    for match in SRC_PATTERN.findall(html_bytes):
        try:
            url = match.decode('utf-8', errors='ignore')
            if url not in seen:
                seen.add(url)
                result.append(url)
        except:
            pass
    
    return result


cpdef int count_links_total(str html):
    """
    Швидкий підрахунок загальної кількості посилань.
    
    Args:
        html: HTML контент
        
    Returns:
        Загальна кількість посилань
    """
    if html is None:
        return 0
    
    cdef bytes html_bytes = html.encode('utf-8', errors='ignore')
    return len(HREF_PATTERN.findall(html_bytes))


cpdef tuple count_links(str html, str base_domain=None):
    """
    Підрахунок внутрішніх та зовнішніх посилань.
    
    Args:
        html: HTML контент
        base_domain: Базовий домен для визначення internal/external
        
    Returns:
        Tuple (internal_count, external_count, total)
        
    Note:
        Якщо base_domain не передано, всі посилання вважаються external.
    """
    if html is None:
        return (0, 0, 0)
    
    cdef bytes html_bytes = html.encode('utf-8', errors='ignore')
    cdef list matches = HREF_PATTERN.findall(html_bytes)
    cdef int total = len(matches)
    cdef int internal_count = 0
    cdef int external_count = 0
    cdef bytes match
    cdef str url
    cdef str domain
    
    if base_domain is None:
        # Без base_domain не можемо визначити internal/external
        return (0, total, total)
    
    cdef str base_domain_lower = base_domain.lower()
    
    for match in matches:
        try:
            url = match.decode('utf-8', errors='ignore')
        except:
            external_count += 1
            continue
        
        # Skip non-http links
        if not (url[:7] == 'http://' or url[:8] == 'https://'):
            # Relative URLs are internal
            if not url.startswith(('javascript:', 'mailto:', 'tel:', '#', 'data:')):
                internal_count += 1
            continue
        
        # Extract domain from URL
        domain = _get_domain_inline(url)
        if domain is None:
            external_count += 1
            continue
        
        # Compare domains (case-insensitive)
        domain_lower = domain.lower()
        if domain_lower == base_domain_lower or domain_lower.endswith('.' + base_domain_lower):
            internal_count += 1
        else:
            external_count += 1
    
    return (internal_count, external_count, total)
