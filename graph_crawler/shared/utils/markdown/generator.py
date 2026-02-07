"""Markdown Generator - Core Implementation.

Standalone утиліта для генерації Markdown з HTML.
Швидка, асинхронна, налаштовувана.

Дизайн:
- НЕ плагін - викликається вибірково коли потрібно
- Працює з BaseTreeAdapter АБО з HTML string
- Оптимізовано для швидкості
- Thread-safe
"""

import logging
import re
import threading
from copy import deepcopy
from functools import lru_cache
from typing import Any, Dict, List, Optional, Tuple, Union

from graph_crawler.shared.utils.markdown.options import MarkdownOptions
from graph_crawler.shared.utils.markdown.result import MarkdownResult

logger = logging.getLogger(__name__)

# Thread-safe lazy import з кешуванням
_bs4_lock = threading.Lock()
_bs4_cache = {}


def _get_bs4():
    """Thread-safe lazy import BeautifulSoup."""
    if 'BeautifulSoup' not in _bs4_cache:
        with _bs4_lock:
            if 'BeautifulSoup' not in _bs4_cache:
                from bs4 import BeautifulSoup
                _bs4_cache['BeautifulSoup'] = BeautifulSoup
    return _bs4_cache['BeautifulSoup']


class MarkdownGenerator:
    """
    Генератор Markdown з HTML.
    
    Standalone утиліта - викликається коли потрібно, не плагін.
    Thread-safe, можна використовувати в багатопоточному середовищі.
    
    Підтримує:
    1. Генерація з HTML string (основний метод)
    2. Генерація з BaseTreeAdapter (оптимізовано - без повторного парсингу)
    
    Приклад:
        >>> md = MarkdownGenerator()
        >>> result = md.generate(html_string)
        >>> print(result.fit_markdown)
        
        >>> # З опціями
        >>> md = MarkdownGenerator(options=MarkdownOptions(
        ...     include_links=False,
        ...     remove_ads=True,
        ... ))
        
        >>> # Статичний метод для простих випадків
        >>> result = MarkdownGenerator.quick_generate(html)
    """
    
    __slots__ = ('options',)
    
    def __init__(self, options: Optional[MarkdownOptions] = None):
        """
        Ініціалізує MarkdownGenerator.
        
        Args:
            options: Налаштування генерації (опціонально)
        """
        self.options = options or MarkdownOptions()
    
    @staticmethod
    def quick_generate(html: str) -> MarkdownResult:
        """
        Статичний метод для швидкої генерації з дефолтними опціями.
        
        Для простих випадків коли не потрібна кастомізація.
        
        Args:
            html: HTML string
            
        Returns:
            MarkdownResult
        """
        return MarkdownGenerator().generate_from_html(html)
    
    def generate(self, source: Union[str, Any]) -> MarkdownResult:
        """
        Генерує Markdown з HTML або adapter.
        
        Універсальний метод - автоматично визначає тип input.
        
        Args:
            source: HTML string або BaseTreeAdapter
            
        Returns:
            MarkdownResult з різними варіантами тексту
        """
        if isinstance(source, str):
            return self.generate_from_html(source)
        
        # Припускаємо що це adapter з методом parse
        if hasattr(source, 'tree') and hasattr(source, 'find_all'):
            return self.generate_from_adapter(source)
        
        logger.warning(f"Unknown source type: {type(source)}")
        return MarkdownResult.empty()
    
    def generate_from_html(self, html: str) -> MarkdownResult:
        """
        Генерує Markdown з HTML string.
        
        Основний метод для standalone використання.
        
        Args:
            html: HTML string
            
        Returns:
            MarkdownResult
        """
        if not html or not html.strip():
            return MarkdownResult.empty()
        
        BeautifulSoup = _get_bs4()
        
        try:
            soup = BeautifulSoup(html, 'lxml')
            return self._process_soup(soup, html)
        except ImportError:
            # Fallback to html.parser якщо lxml недоступний
            try:
                soup = BeautifulSoup(html, 'html.parser')
                return self._process_soup(soup, html)
            except (ValueError, AttributeError, TypeError) as e:
                logger.error(f"Failed to parse HTML: {e}")
                return MarkdownResult.empty()
        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"Error generating markdown: {e}")
            return MarkdownResult.empty()
    
    def generate_from_adapter(self, adapter: Any) -> MarkdownResult:
        """
        Генерує Markdown з BaseTreeAdapter.
        
        Оптимальний метод - дерево вже парсоване!
        
        Args:
            adapter: BaseTreeAdapter instance
            
        Returns:
            MarkdownResult
        """
        try:
            tree = adapter.tree
            
            # Перевіряємо тип дерева
            if hasattr(tree, 'find_all'):  # BeautifulSoup
                # Отримуємо HTML для raw_markdown
                html_str = str(tree)
                return self._process_soup(tree, html_str)
            elif hasattr(tree, 'cssselect'):  # lxml
                return self._process_lxml(tree)
            else:
                # Fallback: витягуємо текст через adapter
                text = adapter.text if hasattr(adapter, 'text') else ''
                return MarkdownResult(text=text, fit_markdown=text)
                
        except (ValueError, AttributeError, TypeError) as e:
            logger.error(f"Error generating markdown from adapter: {e}")
            return MarkdownResult.empty()
    
    def _process_soup(self, soup, original_html: str) -> MarkdownResult:
        """
        Обробляє BeautifulSoup дерево.
        
        Args:
            soup: BeautifulSoup object
            original_html: Оригінальний HTML для raw_markdown
            
        Returns:
            MarkdownResult
        """
        BeautifulSoup = _get_bs4()
        
        # 1. Витягуємо метадані ДО очищення
        title = self._extract_title(soup)
        h1 = self._extract_h1(soup)
        description = self._extract_description(soup)
        
        # 2. Генеруємо raw_markdown з ОРИГІНАЛЬНОГО HTML (без копіювання soup)
        # Це економить пам'ять - не дублюємо soup
        raw_soup = BeautifulSoup(original_html, 'lxml')
        self._remove_scripts_only(raw_soup)  # Тільки scripts, не noise
        raw_markdown, _ = self._soup_to_markdown(raw_soup)
        
        # 3. Очищуємо основний soup для fit_markdown
        self._remove_noise(soup)
        
        # 4. Генеруємо fit_markdown
        fit_markdown, stats = self._soup_to_markdown(soup)
        
        # 5. Чистий текст
        text = self._extract_text(soup)
        
        # 6. Перевірка довжини
        is_truncated = False
        if len(text) > self.options.max_length:
            text = text[:self.options.max_length]
            is_truncated = True
        
        # 7. Citations (якщо потрібно) - НА КОПІЇ soup
        md_citations = ""
        references = []
        if self.options.generate_citations:
            # Створюємо копію для citations щоб не модифікувати оригінал
            citations_soup = BeautifulSoup(original_html, 'lxml')
            self._remove_noise(citations_soup)
            md_citations, references = self._generate_citations(citations_soup)
        
        return MarkdownResult(
            text=text,
            raw_markdown=raw_markdown,
            fit_markdown=fit_markdown,
            markdown_with_citations=md_citations,
            references=references,
            title=title,
            h1=h1,
            description=description,
            word_count=len(text.split()),
            char_count=len(text),
            heading_count=stats.get('headings', 0),
            link_count=stats.get('links', 0),
            image_count=stats.get('images', 0),
            is_truncated=is_truncated,
        )
    
    def _process_lxml(self, tree) -> MarkdownResult:
        """
        Обробляє lxml дерево.
        
        Args:
            tree: lxml.html.HtmlElement
            
        Returns:
            MarkdownResult
        """
        try:
            from lxml import html
            html_str = html.tostring(tree, encoding='unicode')
            return self.generate_from_html(html_str)
        except ImportError:
            logger.error("lxml not available for processing")
            return MarkdownResult.empty()
    
    def _remove_scripts_only(self, soup) -> None:
        """
        Видаляє тільки технічні теги (scripts, styles).
        
        Для raw_markdown - зберігаємо весь контент крім скриптів.
        
        Args:
            soup: BeautifulSoup object
        """
        for tag_name in ('script', 'style', 'noscript', 'template'):
            for tag in soup.find_all(tag_name):
                tag.decompose()
    
    def _remove_noise(self, soup) -> None:
        """
        Видаляє noise елементи з soup.
        
        Модифікує soup in-place.
        Оптимізовано: один прохід для всіх тегів.
        
        Args:
            soup: BeautifulSoup object
        """
        # 1. Збираємо всі теги для видалення в один список
        tags_to_remove = set(self.options.noise_tags)
        
        if self.options.remove_nav:
            tags_to_remove.add('nav')
        if self.options.remove_header:
            tags_to_remove.add('header')
        if self.options.remove_footer:
            tags_to_remove.add('footer')
        if self.options.remove_aside:
            tags_to_remove.add('aside')
        if self.options.remove_buttons:
            tags_to_remove.add('button')
        
        # Один прохід для всіх тегів
        for tag in soup.find_all(list(tags_to_remove)):
            tag.decompose()
        
        # 2. Видаляємо за класами та ID (якщо потрібно)
        if self.options.remove_ads:
            # Функція для перевірки класів/id
            def should_remove(tag):
                if not hasattr(tag, 'get'):
                    return False
                
                # Перевірка класів
                classes = tag.get('class', [])
                if classes:
                    class_str = ' '.join(classes).lower()
                    if any(nc in class_str for nc in self.options.noise_classes):
                        return True
                
                # Перевірка ID
                tag_id = tag.get('id', '')
                if tag_id:
                    id_lower = tag_id.lower()
                    if any(ni in id_lower for ni in self.options.noise_ids):
                        return True
                
                return False
            
            # Знаходимо всі елементи з class або id атрибутами
            for tag in soup.find_all(lambda t: t.get('class') or t.get('id')):
                if should_remove(tag):
                    tag.decompose()
    
    def _soup_to_markdown(self, soup) -> Tuple[str, Dict[str, int]]:
        """
        Конвертує BeautifulSoup дерево в Markdown.
        
        Використовує set для відстеження оброблених елементів
        щоб уникнути дублювання.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Tuple[markdown_string, stats_dict]
        """
        md_parts = []
        stats = {'headings': 0, 'links': 0, 'images': 0, 'code': 0, 'lists': 0}
        processed_elements = set()
        
        # Знаходимо main content або body
        main = soup.find('main') or soup.find('article') or soup.find('body') or soup
        
        # Обробляємо елементи в порядку появи
        for element in main.descendants:
            if not hasattr(element, 'name') or element.name is None:
                continue
            
            # Пропускаємо вже оброблені елементи
            elem_id = id(element)
            if elem_id in processed_elements:
                continue
            
            tag_name = element.name.lower()
            
            # Заголовки
            if tag_name in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
                level = int(tag_name[1])
                text = element.get_text(strip=True)
                if text and len(text) >= self.options.min_heading_length:
                    md_parts.append(f"\n{'#' * level} {text}\n")
                    stats['headings'] += 1
                processed_elements.add(elem_id)
            
            # Параграфи
            elif tag_name == 'p':
                text = element.get_text(strip=True)
                if text and len(text) >= self.options.min_paragraph_length:
                    # Обробка inline коду
                    md_text = self._process_inline_elements(element)
                    md_parts.append(f"\n{md_text}\n")
                processed_elements.add(elem_id)
            
            # Код (блоки)
            elif tag_name == 'pre' and self.options.include_code_blocks:
                code = element.get_text()
                if code.strip():
                    # Визначаємо мову
                    code_tag = element.find('code')
                    lang = ''
                    if code_tag:
                        classes = code_tag.get('class', [])
                        for cls in classes:
                            if cls.startswith('language-'):
                                lang = cls[9:]
                                break
                            elif cls.startswith('lang-'):
                                lang = cls[5:]
                                break
                    md_parts.append(f"\n```{lang}\n{code.strip()}\n```\n")
                    stats['code'] += 1
                processed_elements.add(elem_id)
                # Маркуємо вкладений code як оброблений
                if code_tag:
                    processed_elements.add(id(code_tag))
            
            # Списки (ul/ol)
            elif tag_name in ('ul', 'ol') and self.options.include_lists:
                list_md = self._process_list(element, tag_name)
                if list_md:
                    md_parts.append(f"\n{list_md}\n")
                    stats['lists'] += 1
                # Маркуємо всі вкладені елементи як оброблені
                for child in element.descendants:
                    if hasattr(child, 'name'):
                        processed_elements.add(id(child))
                processed_elements.add(elem_id)
            
            # Blockquote
            elif tag_name == 'blockquote' and self.options.include_blockquotes:
                text = element.get_text(strip=True)
                if text:
                    lines = text.split('\n')
                    quoted = '\n'.join(f"> {line}" for line in lines if line.strip())
                    md_parts.append(f"\n{quoted}\n")
                processed_elements.add(elem_id)
            
            # Посилання
            elif tag_name == 'a' and self.options.include_links:
                href = element.get('href', '')
                if href:
                    stats['links'] += 1
            
            # Зображення
            elif tag_name == 'img' and self.options.include_images:
                src = element.get('src', '')
                alt = element.get('alt', '')
                if src:
                    md_parts.append(f"\n![{alt}]({src})\n")
                    stats['images'] += 1
                processed_elements.add(elem_id)
            
            # Таблиці
            elif tag_name == 'table' and self.options.include_tables:
                table_md = self._table_to_markdown(element)
                if table_md:
                    md_parts.append(f"\n{table_md}\n")
                # Маркуємо всі вкладені елементи
                for child in element.descendants:
                    if hasattr(child, 'name'):
                        processed_elements.add(id(child))
                processed_elements.add(elem_id)
        
        # Очищуємо і об'єднуємо
        markdown = '\n'.join(md_parts)
        
        # Нормалізуємо пробіли
        if self.options.normalize_whitespace:
            markdown = re.sub(r'\n{3,}', '\n\n', markdown)
            markdown = markdown.strip()
        
        return markdown, stats
    
    def _process_inline_elements(self, element) -> str:
        """
        Обробляє inline елементи в параграфі (code, strong, em).
        
        Args:
            element: BeautifulSoup element
            
        Returns:
            Markdown string з форматуванням
        """
        result = []
        for child in element.children:
            if hasattr(child, 'name'):
                if child.name == 'code':
                    result.append(f"`{child.get_text()}`")
                elif child.name in ('strong', 'b'):
                    result.append(f"**{child.get_text()}**")
                elif child.name in ('em', 'i'):
                    result.append(f"*{child.get_text()}*")
                elif child.name == 'a' and self.options.include_links:
                    href = child.get('href', '')
                    text = child.get_text(strip=True)
                    if href and text:
                        result.append(f"[{text}]({href})")
                    else:
                        result.append(text)
                else:
                    result.append(child.get_text())
            else:
                # Текстова нода
                result.append(str(child))
        
        return ''.join(result).strip()
    
    def _process_list(self, element, list_type: str, indent: int = 0) -> str:
        """
        Обробляє список з підтримкою вкладеності.
        
        Args:
            element: ul або ol елемент
            list_type: 'ul' або 'ol'
            indent: Рівень вкладеності
            
        Returns:
            Markdown string
        """
        lines = []
        indent_str = "  " * indent
        
        items = element.find_all('li', recursive=False)
        for i, li in enumerate(items):
            # Отримуємо текст тільки прямих текстових нод
            direct_text = ''
            for child in li.children:
                if not hasattr(child, 'name'):
                    direct_text += str(child)
                elif child.name not in ('ul', 'ol'):
                    direct_text += child.get_text()
            
            direct_text = ' '.join(direct_text.split()).strip()
            
            if direct_text:
                if list_type == 'ol':
                    lines.append(f"{indent_str}{i+1}. {direct_text}")
                else:
                    lines.append(f"{indent_str}- {direct_text}")
            
            # Обробляємо вкладені списки
            for nested in li.find_all(['ul', 'ol'], recursive=False):
                nested_md = self._process_list(nested, nested.name, indent + 1)
                if nested_md:
                    lines.append(nested_md)
        
        return '\n'.join(lines)
    
    def _table_to_markdown(self, table) -> str:
        """
        Конвертує HTML таблицю в Markdown.
        
        Args:
            table: BeautifulSoup table element
            
        Returns:
            Markdown string
        """
        rows = []
        header_found = False
        
        # Спочатку шукаємо header в thead
        thead = table.find('thead')
        if thead:
            header_row = thead.find('tr')
            if header_row:
                cells = [th.get_text(strip=True) for th in header_row.find_all(['th', 'td'])]
                if cells:
                    rows.append('| ' + ' | '.join(cells) + ' |')
                    rows.append('| ' + ' | '.join(['---'] * len(cells)) + ' |')
                    header_found = True
        
        # Body
        tbody = table.find('tbody') or table
        all_trs = tbody.find_all('tr')
        
        for idx, tr in enumerate(all_trs):
            # Пропускаємо header rows з thead
            if tr.parent and tr.parent.name == 'thead':
                continue
            
            cells = [td.get_text(strip=True) for td in tr.find_all(['td', 'th'])]
            if not cells:
                continue
            
            # Якщо немає header і це перший row
            if not header_found and not rows:
                # Перевіряємо чи це header row (th елементи)
                if tr.find('th'):
                    rows.append('| ' + ' | '.join(cells) + ' |')
                    rows.append('| ' + ' | '.join(['---'] * len(cells)) + ' |')
                    header_found = True
                else:
                    # Створюємо generic header
                    rows.append('| ' + ' | '.join([f'Col {i+1}' for i in range(len(cells))]) + ' |')
                    rows.append('| ' + ' | '.join(['---'] * len(cells)) + ' |')
                    rows.append('| ' + ' | '.join(cells) + ' |')
                    header_found = True
            else:
                rows.append('| ' + ' | '.join(cells) + ' |')
        
        return '\n'.join(rows)
    
    def _extract_text(self, soup) -> str:
        """
        Витягує чистий текст з soup.
        
        Args:
            soup: BeautifulSoup object
            
        Returns:
            Clean text string
        """
        raw = soup.get_text(separator=" ", strip=True)
        
        if self.options.normalize_whitespace:
            return " ".join(raw.split())
        return raw
    
    def _extract_title(self, soup) -> str:
        """Витягує title."""
        title_tag = soup.find('title')
        return title_tag.get_text(strip=True) if title_tag else ''
    
    def _extract_h1(self, soup) -> str:
        """Витягує перший H1."""
        h1_tag = soup.find('h1')
        return h1_tag.get_text(strip=True) if h1_tag else ''
    
    def _extract_description(self, soup) -> str:
        """Витягує meta description."""
        meta = soup.find('meta', attrs={'name': 'description'})
        if meta:
            return meta.get('content', '')
        
        # Fallback: og:description
        og_meta = soup.find('meta', attrs={'property': 'og:description'})
        if og_meta:
            return og_meta.get('content', '')
        
        return ''
    
    def _generate_citations(self, soup) -> Tuple[str, List[Dict[str, str]]]:
        """
        Генерує Markdown з citations [1], [2].
        
        ВАЖЛИВО: Працює на КОПІЇ soup, не модифікує оригінал!
        
        Args:
            soup: BeautifulSoup object (копія)
            
        Returns:
            Tuple[markdown_with_citations, references_list]
        """
        references = []
        ref_counter = 1
        
        # Знаходимо всі посилання
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            text = a.get_text(strip=True)
            
            if href and text and not href.startswith('#'):
                references.append({
                    'id': ref_counter,
                    'text': text,
                    'url': href,
                })
                # Замінюємо посилання на citation
                a.replace_with(f"{text} [{ref_counter}]")
                ref_counter += 1
        
        # Генеруємо markdown
        md, _ = self._soup_to_markdown(soup)
        
        # Додаємо references в кінці
        if references:
            md += "\n\n## References\n\n"
            for ref in references:
                md += f"[{ref['id']}] {ref['url']}\n"
        
        return md, references


# Async версія для асинхронного використання
async def generate_markdown_async(
    html: str,
    options: Optional[MarkdownOptions] = None,
) -> MarkdownResult:
    """
    Асинхронна генерація Markdown.
    
    Виконується в thread executor для non-blocking операції.
    Сумісно з Python 3.9+.
    
    Args:
        html: HTML string
        options: MarkdownOptions (опціонально)
        
    Returns:
        MarkdownResult
    """
    import asyncio
    
    generator = MarkdownGenerator(options)
    
    # Python 3.9+ compatible
    try:
        # Preferred method for Python 3.9+
        return await asyncio.to_thread(generator.generate_from_html, html)
    except AttributeError:
        # Fallback for older Python versions
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            generator.generate_from_html,
            html,
        )
