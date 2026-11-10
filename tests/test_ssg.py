import os
import sys

if sys.prefix == sys.base_prefix:
    for _venv_py in (".venv/bin/python", ".venv/Scripts/python.exe"):
        if os.path.exists(_venv_py):
            if "unittest" in sys.argv[0]:
                os.execv(_venv_py, [_venv_py, "-m", "unittest", *sys.argv[1:]])
            else:
                os.execv(_venv_py, [_venv_py, *sys.argv])

import unittest
import tempfile
from datetime import date, datetime

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.main import (
    safe_parse_date,
    _safe_tag_slug,
    parse_file,
    build_markdown,
    ImageReplacementParser,
    scaffold_content,
    check_site,
)


class TestSafeParseDate(unittest.TestCase):
    def test_iso_string(self):
        d = safe_parse_date("2025-07-30")
        self.assertEqual(d, datetime(2025, 7, 30))

    def test_date_object(self):
        d = safe_parse_date(date(2025, 7, 30))
        self.assertEqual(d, datetime(2025, 7, 30))

    def test_invalid_string(self):
        self.assertIsNone(safe_parse_date("invalid-date-string"))
        self.assertIsNone(safe_parse_date(None))
        self.assertIsNone(safe_parse_date(""))


class TestTagSlug(unittest.TestCase):
    def test_safe_slug(self):
        self.assertEqual(_safe_tag_slug("web / dev"), "web-dev")
        self.assertEqual(_safe_tag_slug("../tag"), "tag")
        self.assertEqual(_safe_tag_slug(""), "tag")
        self.assertEqual(_safe_tag_slug("  hello world!  "), "hello-world")

    def test_tag_deduplication(self):
        raw_tags = ["news", "web / dev", "news", "web-dev"]
        slugs = list(dict.fromkeys(_safe_tag_slug(t) for t in raw_tags))
        self.assertEqual(slugs, ["news", "web-dev"])


class TestParseFile(unittest.TestCase):
    def setUp(self):
        self.md = build_markdown("native")

    def test_h1_extraction_ignores_code_comments(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "test.md")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "layout: post\n"
                    "---\n"
                    "```python\n"
                    "# This comment must NOT become title\n"
                    "x = 1\n"
                    "```\n\n"
                    "# Actual Title\n\n"
                    "Body text here.\n"
                )
            page_data, html = parse_file(fpath, "native", md=self.md)
            self.assertEqual(page_data.get("title"), "Actual Title")
            # Inferred title strips leading <h1> to prevent duplicate header
            self.assertNotIn("<h1>Actual Title</h1>", html)

    def test_reading_time_and_excerpt(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "excerpt.md")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "title: Excerpt Test\n"
                    "---\n"
                    "<pre>Ignored pre block</pre>\n\n"
                    "<p>First paragraph with &amp; unescaped entities.</p>\n"
                )
            page_data, html = parse_file(fpath, "native", md=self.md)
            self.assertEqual(page_data.get("reading_time"), 1)
            self.assertIn("& unescaped entities", page_data.get("excerpt", ""))
            self.assertNotIn("Ignored pre block", page_data.get("excerpt", ""))

    def test_layout_inference(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # posts directory
            posts_dir = os.path.join(tmpdir, "posts")
            os.makedirs(posts_dir)
            p_post = os.path.join(posts_dir, "post1.md")
            with open(p_post, "w", encoding="utf-8") as f:
                f.write("# Post Title\n")

            # docs directory
            docs_dir = os.path.join(tmpdir, "docs")
            os.makedirs(docs_dir)
            p_doc = os.path.join(docs_dir, "doc1.md")
            with open(p_doc, "w", encoding="utf-8") as f:
                f.write("# Doc Title\n")

            # root page
            p_page = os.path.join(tmpdir, "about.md")
            with open(p_page, "w", encoding="utf-8") as f:
                f.write("# About Title\n")

            pd_post, _ = parse_file(p_post, "native", md=self.md, content_dir=tmpdir)
            pd_doc, _ = parse_file(p_doc, "native", md=self.md, content_dir=tmpdir)
            pd_page, _ = parse_file(p_page, "native", md=self.md, content_dir=tmpdir)

            self.assertEqual(pd_post.get("layout"), "post")
            self.assertEqual(pd_doc.get("layout"), "docs")
            self.assertEqual(pd_page.get("layout"), "page")

    def test_non_dict_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "list_fm.md")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("---\n- item1\n- item2\n---\n# Title\nSome body.\n")
            page_data, html = parse_file(fpath, "native", md=self.md, content_dir=tmpdir)
            self.assertIsNotNone(page_data)
            self.assertEqual(page_data.get("title"), "Title")

    def test_custom_permalink(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fpath = os.path.join(tmpdir, "item.md")
            with open(fpath, "w", encoding="utf-8") as f:
                f.write(
                    "---\n"
                    "permalink: /custom/article.html\n"
                    "---\n"
                    "# Hello\n"
                )
            page_data, _ = parse_file(fpath, "native", md=self.md)
            self.assertEqual(page_data.get("url"), "/custom/article")


class TestImageReplacementParser(unittest.TestCase):
    def setUp(self):
        self.manifest = {
            "hero.png": {
                "webp": [{"width": 640, "path": "assets/images-processed/hero-640.webp"}],
                "jpg": [{"width": 640, "path": "assets/images-processed/hero-640.jpg"}],
            }
        }

    def test_picture_wrapping(self):
        parser = ImageReplacementParser(self.manifest)
        parser.feed('<img src="/assets/images/hero.png" alt="Hero">')
        parser.close()
        out = parser.get_html()
        self.assertIn("<picture>", out)
        self.assertIn('<source type="image/webp"', out)
        self.assertIn('alt="Hero"', out)

    def test_ignore_external_url(self):
        parser = ImageReplacementParser(self.manifest)
        raw = '<img src="https://example.com/assets/images/hero.png">'
        parser.feed(raw)
        parser.close()
        self.assertEqual(parser.get_html(), raw)

    def test_ignore_nested_picture(self):
        parser = ImageReplacementParser(self.manifest)
        raw = '<picture><img src="/assets/images/hero.png"></picture>'
        parser.feed(raw)
        parser.close()
        self.assertEqual(parser.get_html(), raw)


class TestScaffoldAndCheckSite(unittest.TestCase):
    def test_scaffold_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = scaffold_content("My Awesome Post", kind="post", content_dir=tmpdir)
            self.assertTrue(os.path.exists(target))
            with open(target, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn('title: "My Awesome Post"', content)
            self.assertIn('layout: "post"', content)

            # Duplicate raises SystemExit
            with self.assertRaises(SystemExit):
                scaffold_content("My Awesome Post", kind="post", content_dir=tmpdir)

            # Inferred kind from prefix
            doc_target = scaffold_content("docs/api-guide", content_dir=tmpdir)
            self.assertTrue(os.path.exists(doc_target))
            with open(doc_target, "r", encoding="utf-8") as f:
                doc_content = f.read()
            self.assertIn('layout: "docs"', doc_content)

    def test_scaffold_quotes_in_title_valid_yaml(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = os.path.join(tmpdir, "config.yaml")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write("site_name: TestSite\nbase_url: https://example.com\n")
            tmpl_dir = os.path.join(tmpdir, "templates")
            os.makedirs(tmpl_dir)
            with open(os.path.join(tmpl_dir, "post.html"), "w", encoding="utf-8") as f:
                f.write("{{ content }}")

            target = scaffold_content('Why "Static" Sites Win', kind="post", content_dir=tmpdir)
            self.assertTrue(os.path.exists(target))
            errors, warnings = check_site(
                config_path=cfg,
                content_dir=tmpdir,
                template_dir=tmpl_dir,
                exit_on_error=False,
            )
            self.assertEqual(errors, [])

    def test_scaffold_traversal_sanitization(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = scaffold_content("docs/../../etc/passwd", content_dir=tmpdir)
            self.assertTrue(os.path.exists(target))
            self.assertTrue(target.endswith(os.path.join("docs", "etc", "passwd.md")))
            self.assertTrue(target.startswith(tmpdir))

    def test_check_site_valid(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = os.path.join(tmpdir, "config.yaml")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write("site_name: TestSite\nbase_url: https://example.com\n")

            tmpl_dir = os.path.join(tmpdir, "templates")
            os.makedirs(tmpl_dir)
            with open(os.path.join(tmpl_dir, "post.html"), "w", encoding="utf-8") as f:
                f.write("{{ content }}")
            with open(os.path.join(tmpl_dir, "page.html"), "w", encoding="utf-8") as f:
                f.write("{{ content }}")

            cnt_dir = os.path.join(tmpdir, "content")
            os.makedirs(cnt_dir)
            with open(os.path.join(cnt_dir, "test.md"), "w", encoding="utf-8") as f:
                f.write("---\ntitle: Page\nlayout: page\n---\nHello\n")

            errors, warnings = check_site(
                config_path=cfg,
                content_dir=cnt_dir,
                template_dir=tmpl_dir,
                exit_on_error=False,
            )
            self.assertEqual(errors, [])

    def test_check_site_duplicate_url(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = os.path.join(tmpdir, "config.yaml")
            with open(cfg, "w", encoding="utf-8") as f:
                f.write("site_name: TestSite\nbase_url: https://example.com\n")

            tmpl_dir = os.path.join(tmpdir, "templates")
            os.makedirs(tmpl_dir)
            with open(os.path.join(tmpl_dir, "post.html"), "w", encoding="utf-8") as f:
                f.write("{{ content }}")

            cnt_dir = os.path.join(tmpdir, "content")
            os.makedirs(cnt_dir)
            with open(os.path.join(cnt_dir, "p1.md"), "w", encoding="utf-8") as f:
                f.write("---\ntitle: One\npermalink: /dup\n---\n")
            with open(os.path.join(cnt_dir, "p2.md"), "w", encoding="utf-8") as f:
                f.write("---\ntitle: Two\npermalink: /dup\n---\n")

            errors, warnings = check_site(
                config_path=cfg,
                content_dir=cnt_dir,
                template_dir=tmpl_dir,
                exit_on_error=False,
            )
            self.assertTrue(any("Duplicate URL" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
