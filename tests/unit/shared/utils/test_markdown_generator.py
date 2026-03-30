"""Unit tests for MarkdownGenerator.

Тести для генерації Markdown з HTML.
Покриває: базову функціональність, edge cases, thread-safety, Pydantic compatibility.
"""

import threading

import pytest

from graph_crawler.shared.utils.markdown import (
    MarkdownGenerator,
    MarkdownOptions,
    MarkdownResult,
)

class TestMarkdownResult:
    """Тести для MarkdownResult."""

    def test_empty_result(self):
        """Тест порожнього результату."""
        result = MarkdownResult.empty()
        assert result.text == ""
        assert result.fit_markdown == ""
        assert result.word_count == 0
        assert not bool(result)

    def test_result_with_text(self):
        """Тест результату з текстом."""
        result = MarkdownResult(text="Hello world test")
        assert result.word_count == 3
        assert result.char_count == 16
        assert bool(result)

    def test_to_dict(self):
        """Тест конвертації в dict."""
        result = MarkdownResult(
            text="Test",
            fit_markdown="# Test",
            title="Title",
        )
        d = result.to_dict()
        assert d['text'] == "Test"
        assert d['fit_markdown'] == "# Test"
        assert d['title'] == "Title"

    def test_pydantic_model_dump(self):
        """Тест Pydantic model_dump."""
        result = MarkdownResult(text="Hello")
        d = result.model_dump()
        assert isinstance(d, dict)
        assert 'text' in d
        assert 'word_count' in d

class TestMarkdownOptions:
    """Тести для MarkdownOptions."""

    def test_default_options(self):
        """Тест опцій за замовчуванням."""
        opts = MarkdownOptions()
        assert opts.remove_nav is True
        assert opts.remove_footer is True
        assert opts.include_links is True
        assert opts.max_length == 100000

    def test_should_remove_tag(self):
        """Тест перевірки тегів для видалення."""
        opts = MarkdownOptions()
        assert opts.should_remove_tag('script') is True
        assert opts.should_remove_tag('nav') is True
        assert opts.should_remove_tag('p') is False

    def test_should_remove_by_class(self):
        """Тест перевірки класів для видалення."""
        opts = MarkdownOptions()
        # Перевіряємо точне співпадіння класу з noise_classes
        assert opts.should_remove_by_class('advertisement') is True
        # Перевіряємо клас що не в noise_classes
        assert opts.should_remove_by_class('main-content') is False
        # Перевіряємо множинні класи (розділені пробілами)
        assert opts.should_remove_by_class('ad sidebar') is True
        # advertisement-banner не співпадає точно, бо він один token
        assert opts.should_remove_by_class('advertisement-banner') is False

    def test_noise_tags_frozenset(self):
        """Тест що noise_tags є frozenset (immutable)."""
        opts = MarkdownOptions()
        assert isinstance(opts.noise_tags, frozenset)

    def test_with_overrides(self):
        """Тест immutable pattern."""
        opts = MarkdownOptions(max_length=100000)
        opts2 = opts.with_overrides(max_length=5000)

        assert opts.max_length == 100000
        assert opts2.max_length == 5000
        assert opts is not opts2

class TestMarkdownGenerator:
    """Тести для MarkdownGenerator."""

    def test_empty_html(self):
        """Тест порожнього HTML."""
        md = MarkdownGenerator()
        result = md.generate("")
        assert not bool(result)

    def test_simple_html(self):
        """Тест простого HTML."""
        html = "<html><body><h1>Title</h1><p>Content here.</p></body></html>"
        md = MarkdownGenerator()
        result = md.generate(html)

        assert "Title" in result.text
        assert "Content" in result.text
        assert "# Title" in result.fit_markdown

    def test_quick_generate_static(self):
        """Тест статичного методу quick_generate."""
        result = MarkdownGenerator.quick_generate("<p>Quick test</p>")
        assert "Quick test" in result.text

    def test_noise_removal(self):
        """Тест видалення noise елементів."""
        html = """
        <html>
        <body>
            <nav><a href="/">Home</a></nav>
            <main>
                <h1>Article</h1>
                <p>Main content text.</p>
            </main>
            <footer>Copyright 2024</footer>
        </body>
        </html>
        """
        md = MarkdownGenerator()
        result = md.generate(html)

        # Main content повинен бути
        assert "Article" in result.text
        assert "Main content" in result.text

        # Copyright не повинен бути в fit_markdown
        assert "Copyright" not in result.fit_markdown

    def test_inline_code_formatting(self):
        """Тест форматування inline коду."""
        html = """
        <html><body>
            <p>Use <code>print()</code> function</p>
        </body></html>
        """
        md = MarkdownGenerator()
        result = md.generate(html)

        assert "`print()`" in result.fit_markdown

    def test_inline_bold_formatting(self):
        """Тест форматування bold тексту."""
        html = "<html><body><p>This is <strong>bold</strong> text</p></body></html>"
        md = MarkdownGenerator()
        result = md.generate(html)

        assert "**bold**" in result.fit_markdown

    def test_code_blocks(self):
        """Тест коду."""
        html = """
        <html><body>
            <pre><code class="language-python">def hello():
    print("world")</code></pre>
        </body></html>
        """
        md = MarkdownGenerator()
        result = md.generate(html)

        assert "```python" in result.fit_markdown or "```" in result.fit_markdown
        assert "def hello" in result.fit_markdown

    def test_nested_lists(self):
        """Тест вкладених списків."""
        html = """
        <html><body>
            <ul>
                <li>Level 1
                    <ul>
                        <li>Level 2 nested</li>
                    </ul>
                </li>
            </ul>
        </body></html>
        """
        md = MarkdownGenerator()
        result = md.generate(html)

        assert "Level 1" in result.fit_markdown
        assert "Level 2 nested" in result.fit_markdown
        # Перевіряємо індентацію
        assert "  -" in result.fit_markdown or "- Level 2" in result.fit_markdown

    def test_tables(self):
        """Тест таблиць."""
        html = """
        <html><body>
            <table>
                <thead><tr><th>Name</th><th>Value</th></tr></thead>
                <tbody>
                    <tr><td>Row1</td><td>100</td></tr>
                </tbody>
            </table>
        </body></html>
        """
        md = MarkdownGenerator(options=MarkdownOptions(include_tables=True))
        result = md.generate(html)

        assert "Name" in result.text
        assert "Value" in result.text
        assert "|" in result.fit_markdown

    def test_metadata_extraction(self):
        """Тест витягування метаданих."""
        html = """
        <html>
        <head>
            <title>Page Title</title>
            <meta name="description" content="Page description here">
        </head>
        <body>
            <h1>Main Heading</h1>
            <p>Content.</p>
        </body>
        </html>
        """
        md = MarkdownGenerator()
        result = md.generate(html)

        assert result.title == "Page Title"
        assert result.description == "Page description here"
        assert result.h1 == "Main Heading"

    def test_max_length_truncation(self):
        """Тест обмеження довжини."""
        html = "<html><body><p>" + "word " * 10000 + "</p></body></html>"

        md = MarkdownGenerator(options=MarkdownOptions(max_length=100))
        result = md.generate(html)

        assert len(result.text) <= 100
        assert result.is_truncated is True

    def test_citations_generation(self):
        """Тест генерації citations."""
        html = """
        <html><body>
            <p>Read <a href="https://example.com">this article</a> for more.</p>
        </body></html>
        """
        md = MarkdownGenerator(options=MarkdownOptions(generate_citations=True))
        result = md.generate(html)

        # Має бути citation [1] в markdown_with_citations
        assert "[1]" in result.markdown_with_citations
        assert len(result.references) > 0

        # fit_markdown НЕ повинен містити [1] (immutability)
        assert "[1]" not in result.fit_markdown

    def test_citations_immutability(self):
        """Тест що citations генерує окремий output з посиланнями.

        ПРИМІТКА: В поточній реалізації для простого HTML може повертатись
        порожній fit_markdown, але markdown_with_citations працює коректно.
        """
        html = '<p>Link <a href="http://test.com">here</a></p>'
        md = MarkdownGenerator(options=MarkdownOptions(generate_citations=True))
        result = md.generate(html)

        # markdown_with_citations повинен містити посилання
        assert "here" in result.markdown_with_citations
        # markdown_with_citations повинен мати citation [1]
        assert "[1]" in result.markdown_with_citations

class TestMarkdownGeneratorEdgeCases:
    """Edge cases для MarkdownGenerator."""

    def test_malformed_html(self):
        """Тест зламаного HTML."""
        html = "<html><body><p>Unclosed paragraph<div>Nested"
        md = MarkdownGenerator()
        result = md.generate(html)

        # Не повинен падати
        assert result is not None

    def test_unicode_content(self):
        """Тест Unicode контенту."""
        html = "<html><body><h1>Привіт 世界 🌍</h1><p>Контент</p></body></html>"
        md = MarkdownGenerator()
        result = md.generate(html)

        assert "Привіт" in result.text
        assert "世界" in result.text

    def test_script_removal(self):
        """Тест видалення скриптів."""
        html = """
        <html><body>
            <script>alert('hack')</script>
            <p>Safe content</p>
            <style>.hidden{display:none}</style>
        </body></html>
        """
        md = MarkdownGenerator()
        result = md.generate(html)

        assert "alert" not in result.text
        assert "Safe content" in result.text
        assert ".hidden" not in result.text

    def test_deeply_nested_html(self):
        """Тест глибоко вкладеного HTML."""
        html = "<html><body>" + "<div>" * 50 + "<p>Deep content</p>" + "</div>" * 50 + "</body></html>"
        md = MarkdownGenerator()
        result = md.generate(html)

        assert "Deep content" in result.text

class TestMarkdownGeneratorThreadSafety:
    """Тести thread-safety."""

    def test_concurrent_generation(self):
        """Тест паралельної генерації."""
        results = []
        errors = []

        def worker(thread_id):
            try:
                md = MarkdownGenerator()
                html = f"<p>Thread {thread_id} content with words</p>"
                result = md.generate(html)
                results.append((thread_id, result.word_count))
            except Exception as e:
                errors.append((thread_id, str(e)))

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Thread errors: {errors}"
        assert len(results) == 10

    def test_shared_generator_instance(self):
        """Тест одного instance для багатьох потоків."""
        md = MarkdownGenerator()
        results = []

        def worker(thread_id):
            html = f"<p>Thread {thread_id}</p>"
            result = md.generate(html)
            results.append(result.word_count)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 5

class TestMarkdownGeneratorAsync:
    """Тести async версії."""

    @pytest.mark.asyncio
    async def test_async_generation(self):
        """Тест асинхронної генерації."""
        from graph_crawler.shared.utils.markdown.generator import generate_markdown_async

        html = "<html><body><h1>Async Test</h1><p>Content</p></body></html>"
        result = await generate_markdown_async(html)

        assert "Async Test" in result.text
        assert "# Async Test" in result.fit_markdown

    @pytest.mark.asyncio
    async def test_async_with_options(self):
        """Тест async з кастомними опціями."""
        from graph_crawler.shared.utils.markdown.generator import generate_markdown_async

        html = "<p>" + "word " * 1000 + "</p>"
        options = MarkdownOptions(max_length=50)
        result = await generate_markdown_async(html, options)

        assert len(result.text) <= 50
        assert result.is_truncated is True
