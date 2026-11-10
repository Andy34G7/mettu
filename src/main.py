import os
import sys

if __name__ == "__main__" and sys.prefix == sys.base_prefix:
    for _venv_py in (".venv/bin/python", ".venv/Scripts/python.exe"):
        if os.path.exists(_venv_py):
            os.execv(_venv_py, [_venv_py, *sys.argv])

import yaml
import markdown
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import date, datetime, timezone
import argparse
import shutil
import json
import re
from collections import defaultdict
from html import escape, unescape
from html.parser import HTMLParser
try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass
from pygments.formatters import HtmlFormatter
from pygments.util import ClassNotFound

DEFAULT_PYGMENTS_THEME = "native"
TEMPLATE_DIR = "templates"
CONFIG_FILE = "config.yaml"
OUTPUT_DIR = "."
IMAGES_DIR = "assets/images"
CONTENT_DIR = "content"

PAGE_SLUG_CACHE = ".cache/page-slugs.json"
PAGE_PARSE_CACHE = ".cache/page-cache.json"
IMAGE_MANIFEST_PATH = ".cache/image-manifest.json"
GENERATED_THEME_PATH = "assets/css/generated.daisyui.css"
GENERATED_FONTS_PATH = "assets/css/generated.fonts.css"
GENERATED_SYNTAX_PATH = "assets/css/syntax.css"

PRESERVED_ROOTS = {
    ".git",
    ".github",
    ".cache",
    ".venv",
    "assets",
    "content",
    "dist",
    "node_modules",
    "src",
    "templates",
    "scripts",
    "public",
    "tests",
    "config.yaml",
    "package.json",
    "package-lock.json",
    "requirements.txt",
    "vite.config.mjs",
    "README.md",
    "LICENSE.md",
    "CONTRIBUTING.md",
    ".env",
    ".env.example",
    ".gitignore",
    ".dockerignore",
    "Dockerfile",
}


def load_previous_slugs():
    try:
        with open(PAGE_SLUG_CACHE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_current_slugs(slugs):
    os.makedirs(os.path.dirname(PAGE_SLUG_CACHE), exist_ok=True)
    try:
        with open(PAGE_SLUG_CACHE, "w", encoding="utf-8") as f:
            json.dump(sorted(slugs), f)
    except OSError as e:
        print(f"Warning: Could not save slug cache: {e}")


def load_page_cache():
    try:
        with open(PAGE_PARSE_CACHE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_page_cache(cache):
    os.makedirs(os.path.dirname(PAGE_PARSE_CACHE), exist_ok=True)
    try:
        payload = json.dumps(cache, default=str)
        with open(PAGE_PARSE_CACHE, "w", encoding="utf-8") as f:
            f.write(payload)
    except (OSError, TypeError) as e:
        print(f"Warning: Could not save page parse cache: {e}")


def _write_if_changed(path, content):
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                if f.read() == content:
                    return False
        except OSError:
            pass
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except OSError as e:
        print(f"Error: Failed to write {path}: {e}")
        return False


def clean_output(directory):
    print("Cleaning old build files...")
    for name in os.listdir(directory):
        if name in PRESERVED_ROOTS or name.startswith("."):
            continue

        path = os.path.join(directory, name)
        try:
            if os.path.isfile(path) or os.path.islink(path):
                os.remove(path)
                print(f"Deleted file: {path}")
            elif os.path.isdir(path):
                shutil.rmtree(path)
                print(f"Deleted directory: {path}")
        except Exception as e:
            print(f"Failed to delete {path}: {e}")

    print("Cleanup complete.")


def safe_parse_date(date_value):

    if not date_value:
        return None

    if isinstance(date_value, datetime):
        return date_value

    if isinstance(date_value, date):
        return datetime(date_value.year, date_value.month, date_value.day)

    if isinstance(date_value, str):
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y/%m/%d",
            "%d-%m-%Y",
            "%d/%m/%Y",
            "%Y-%m",
            "%Y",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_value, fmt)
            except ValueError:
                continue
        
        try:
            return datetime.fromisoformat(date_value)
        except ValueError:
            pass

    print(f"Warning: Could not parse date: {date_value}")
    return None


def _ensure_sequence(value):
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if item is not None]
    return [value]


def _format_css_scalar(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, str):
        if not value:
            return '""'
        if re.search(r"[\s;:\"]", value):
            return json.dumps(value)
        return value
    return json.dumps(value)


def normalize_theme_config(config):
    theme_config = config.get("theme")

    if isinstance(theme_config, str):
        base = {"default": theme_config}
    elif isinstance(theme_config, dict):
        base = dict(theme_config)
    else:
        base = {}

    default_theme = (
        base.get("default")
        or base.get("preset")
        or base.get("name")
        or "dracula"
    )

    include_candidates = base.get("include") or base.get("presets") or []
    include_list = _ensure_sequence(include_candidates)

    ordered = []
    seen = set()
    if default_theme:
        seen.add(default_theme)
        ordered.append(default_theme)

    for entry in include_list:
        if not entry:
            continue
        name = str(entry).strip()
        if not name or name in seen:
            continue
        ordered.append(name)
        seen.add(name)

    normalized = dict(base)
    normalized["default"] = default_theme
    normalized["include"] = ordered  

    config["theme"] = normalized
    return normalized


def write_theme_file(config, output_path=GENERATED_THEME_PATH):
    theme = config.get("theme") or {}
    names = theme.get("include") or []

    css_blocks = []
    if names:
        joined_names = ", ".join(names)
        css_blocks.append(f'@plugin "daisyui" {{\n  themes: {joined_names};\n}}')
    else:
        css_blocks.append('@plugin "daisyui" {\n  themes: all;\n}')

    custom = theme.get("custom")
    custom_items = custom.items() if isinstance(custom, dict) else []
    default_theme = theme.get("default")

    for name, values in custom_items:
        if not name or not values:
            continue

        lines = ['@plugin "daisyui/theme" {']
        
        # Determine strict defaults
        is_default = bool(default_theme and default_theme == name)
        
        if isinstance(values, str):
            # Raw css mode
            # We still need to provide name and default properties for daisyui plugin to work
            lines.append(f"  name: {_format_css_scalar(name)};")
            lines.append(f"  default: {_format_css_scalar(is_default)};")
            lines.append(values)
        elif isinstance(values, dict):
            seen_keys = set()
            
            theme_name = values.get("name") if isinstance(values.get("name"), str) else None
            theme_name = theme_name.strip() if theme_name else name
            lines.append(f"  name: {_format_css_scalar(theme_name)};")
            seen_keys.add("name")

            lines.append(f"  default: {_format_css_scalar(values.get('default', is_default))};")
            seen_keys.add("default")

            for key, value in values.items():
                if key in seen_keys:
                    continue
                lines.append(f"  {key}: {_format_css_scalar(value)};")
                seen_keys.add(key)
        else:
            continue

        lines.append("}")
        css_blocks.append("\n".join(lines))

    css_content = "\n\n".join(css_blocks) + "\n"
    _write_if_changed(output_path, css_content)


def _normalize_font_family(value):
    if value is None:
        return None
    if isinstance(value, (list, tuple, set)):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(parts) if parts else None
    text = str(value).strip()
    return text or None


def _css_safe_key(name):
    slug = re.sub(r"[^a-z0-9-]+", "-", str(name).strip().lower())
    slug = slug.strip("-")
    return slug or "custom"


def write_font_file(config, output_path=GENERATED_FONTS_PATH):
    fonts_config = config.get("fonts") or {}
    import_entries = [
        str(item).strip()
        for item in _ensure_sequence(fonts_config.get("imports") or fonts_config.get("import"))
        if str(item).strip()
    ]

    custom_entries = _ensure_sequence(
        fonts_config.get("custom") or fonts_config.get("inline")
    )

    families_config = fonts_config.get("families")
    if not isinstance(families_config, dict):
        families_config = {}

    default_body = 'system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif'
    default_heading = f"var(--font-body, {default_body})"
    default_mono = (
        'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace'
    )

    variables = []
    seen_keys = set()
    standard_defaults = {
        "body": default_body,
        "heading": default_heading,
        "mono": default_mono,
    }

    for key, fallback in standard_defaults.items():
        custom_value = _normalize_font_family(families_config.get(key))
        variables.append((key, custom_value or fallback))
        seen_keys.add(key)

    for key, value in families_config.items():
        if key in seen_keys:
            continue
        custom_value = _normalize_font_family(value)
        if not custom_value:
            continue
        variables.append((key, custom_value))

    lines = []

    for item in import_entries:
        if item.startswith("@import"):
            lines.append(item if item.endswith(";") else f"{item};")
        else:
            lines.append(f'@import url("{item}");')

    if import_entries:
        lines.append("")

    for entry in custom_entries:
        if isinstance(entry, dict):
            block_lines = ["@font-face {"]
            for prop, value in entry.items():
                formatted = _format_css_scalar(value)
                if not formatted:
                    continue
                block_lines.append(f"  {prop}: {formatted};")
            block_lines.append("}")
            lines.append("\n".join(block_lines))
        elif entry:
            lines.append(str(entry))

    if custom_entries:
        lines.append("")

    if variables:
        lines.append(":root {")
        for key, value in variables:
            lines.append(f"  --font-{_css_safe_key(key)}: {value};")
        lines.append("}")
        lines.append("")

    lines.append("body {")
    lines.append(f"  font-family: var(--font-body, {default_body});")
    lines.append("}")
    lines.append("")

    lines.append("h1, h2, h3, h4, h5, h6 {")
    lines.append(
        f"  font-family: var(--font-heading, var(--font-body, {default_body}));"
    )
    lines.append("}")
    lines.append("")

    lines.append("code, pre, kbd, samp {")
    lines.append(
        f"  font-family: var(--font-mono, {default_mono});"
    )
    lines.append("}")
    lines.append("")

    css_output = "\n".join(lines).rstrip() + "\n"
    _write_if_changed(output_path, css_output)


def resolve_pygments_theme(config):
    syntax_config = config.get("syntax") if isinstance(config, dict) else None
    theme_candidate = None
    if isinstance(syntax_config, dict):
        raw_value = syntax_config.get("pygments_theme") or syntax_config.get("theme")
        if raw_value is not None:
            theme_candidate = str(raw_value).strip()

    if not theme_candidate:
        env_value = os.getenv("PYGMENTIZE_THEME")
        if env_value:
            theme_candidate = env_value.strip()

    theme = theme_candidate or DEFAULT_PYGMENTS_THEME

    if not isinstance(syntax_config, dict):
        syntax_config = {}
        config["syntax"] = syntax_config

    if "pygments_theme" not in syntax_config or not str(syntax_config["pygments_theme"]).strip():
        syntax_config["pygments_theme"] = theme

    syntax_config["pygments_theme_resolved"] = theme
    return theme


def generate_syntax_css(theme, output_path=GENERATED_SYNTAX_PATH):
    try:
        formatter = HtmlFormatter(style=theme)
        active_theme = theme
    except ClassNotFound:
        fallback = DEFAULT_PYGMENTS_THEME
        print(
            f"Warning: Pygments theme '{theme}' not found. Falling back to '{fallback}'."
        )
        formatter = HtmlFormatter(style=fallback)
        active_theme = fallback

    css = formatter.get_style_defs(".highlight") + "\n"
    _write_if_changed(output_path, css)
    return active_theme


def generate_styles(
    config_path=CONFIG_FILE,
    theme_path=GENERATED_THEME_PATH,
    fonts_path=GENERATED_FONTS_PATH,
):
    config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    config = loaded
                else:
                    print(f"Warning: Configuration in {config_path} is not a dictionary. Using defaults.")
        except (OSError, yaml.YAMLError) as e:
            print(f"Warning: Could not read {config_path}: {e}. Using defaults.")
    else:
        print(f"Warning: Configuration file {config_path} not found. Using defaults.")

    normalize_theme_config(config)
    pygments_theme = resolve_pygments_theme(config)
    write_theme_file(config, theme_path)
    write_font_file(config, fonts_path)
    active_theme = generate_syntax_css(pygments_theme)
    config.setdefault("syntax", {})["pygments_theme_resolved"] = active_theme
    return config, active_theme


def build_markdown(pygments_theme, markdown_config=None):
    if markdown_config is None:
        markdown_config = {}

    extensions = []
    extension_configs = {
        "codehilite": {
            "guess_lang": False,
            "noclasses": False,
            "pygments_style": pygments_theme,
            "css_class": "highlight",
        }
    }

    config_extensions = markdown_config.get("extensions")
    
    # Fallback to default if not configured or empty
    if not config_extensions:
        # Replicate the previous default list
        # "fenced_code", "codehilite", "footnotes", "tables", "attr_list", "sane_lists", "md_in_html", toc
        extensions = [
            "fenced_code",
            "codehilite",
            "footnotes",
            "tables",
            "attr_list",
            "sane_lists",
            "md_in_html",
            "toc"
        ]
        extension_configs["toc"] = {"permalink": True}
    else:
        for ext in config_extensions:
            if isinstance(ext, str):
                extensions.append(ext)
            elif isinstance(ext, dict):
                for name, config in ext.items():
                    extensions.append(name)
                    if config:
                        # If the extension is codehilite, we need to merge with existing pygments config
                        if name == "codehilite":
                            current_conf = extension_configs.get("codehilite", {})
                            current_conf.update(config)
                            extension_configs["codehilite"] = current_conf
                        else:
                            extension_configs[name] = config

    
    return markdown.Markdown(
        extensions=extensions, extension_configs=extension_configs
    )


def load_templates(env, template_dir=TEMPLATE_DIR, allowed_extensions=(".html", ".jinja", ".jinja2", ".j2")):
    templates = {}
    for root, _, files in os.walk(template_dir):
        for filename in files:
            if allowed_extensions and not filename.endswith(allowed_extensions):
                continue
            rel_path = os.path.relpath(os.path.join(root, filename), template_dir)
            rel_path = rel_path.replace(os.sep, "/")
            template = env.get_template(rel_path)
            base_name = os.path.splitext(filename)[0]
            rel_without_ext = os.path.splitext(rel_path)[0]
            for key in (rel_path, rel_without_ext, base_name):
                if key not in templates:
                    templates[key] = template
    return templates


def _normalize_yaml_values(obj):
    if isinstance(obj, date):
        return obj.strftime("%Y-%m-%d")
    if isinstance(obj, dict):
        return {k: _normalize_yaml_values(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_yaml_values(v) for v in obj]
    return obj


def _safe_tag_slug(tag):
    s = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(tag).strip()).strip("_-")
    return s or "tag"


def _strip_html(html_str):
    cleaned = re.sub(r'<a[^>]*class="headerlink"[^>]*>.*?</a>', "", html_str, flags=re.DOTALL)
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", cleaned))).strip()


def _clean_toc_tokens(tokens):
    cleaned = []
    for t in tokens or []:
        if isinstance(t, dict):
            cleaned.append({
                **t,
                "name": _strip_html(str(t.get("name", ""))),
                "children": _clean_toc_tokens(t.get("children") or []),
            })
    return cleaned


def _flatten_toc_headings(tokens):
    names = []
    for t in tokens or []:
        if isinstance(t, dict):
            if t.get("name"):
                names.append(t["name"])
            names.extend(_flatten_toc_headings(t.get("children") or []))
    return names


CALLOUT_STYLES = {
    "NOTE": ("alert-info", "Note"),
    "TIP": ("alert-success", "Tip"),
    "IMPORTANT": ("alert-secondary", "Important"),
    "WARNING": ("alert-warning", "Warning"),
    "CAUTION": ("alert-error", "Caution"),
}


def _render_callouts(html_str):
    def _repl(match):
        kind = match.group(1).upper()
        first_body = match.group(2).strip()
        rest_body = match.group(3).strip()
        cls, label = CALLOUT_STYLES.get(kind, ("alert-info", kind.title()))
        inner = f"<p>{first_body}</p>{rest_body}" if first_body else rest_body
        return (
            f'<div role="note" class="alert {cls} my-4 not-prose">'
            f'<div><div class="font-bold text-sm uppercase tracking-wide">{label}</div>'
            f'<div class="text-sm mt-1">{inner}</div></div></div>'
        )

    return re.sub(
        r"<blockquote>\s*<p>\s*\[!(NOTE|TIP|IMPORTANT|WARNING|CAUTION)\](?:<br\s*/?>|\s*\n|\s+)?(.*?)</p>\s*(.*?)</blockquote>",
        _repl,
        html_str,
        flags=re.IGNORECASE | re.DOTALL,
    )


def parse_file(filepath, pygments_theme, markdown_config=None, md=None, page_cache=None, config_hash="", content_dir=CONTENT_DIR):
    rel_path = os.path.relpath(filepath, content_dir).replace(os.sep, "/")
    try:
        st = os.stat(filepath)
    except OSError:
        st = None

    if page_cache is not None and st is not None:
        cached = page_cache.get(rel_path)
        if (
            cached
            and cached.get("mtime_ns") == st.st_mtime_ns
            and cached.get("size") == st.st_size
            and cached.get("config_hash") == config_hash
        ):
            c_data = dict(cached["page_data"])
            c_data["_rel_path"] = rel_path
            return c_data, cached["html_content"]

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            file_content = f.read()
    except OSError as e:
        print(f"Error: Could not read file {filepath}: {e}")
        return None, None

    if file_content.startswith("---"):
        try:
            parts = file_content.split("---", 2)
            if len(parts) < 3:
                page_config = {}
                markdown_data = file_content
            else:
                loaded = yaml.safe_load(parts[1])
                if loaded is not None and not isinstance(loaded, dict):
                    print(f"Warning: Frontmatter in {filepath} is not a dictionary. Ignoring.")
                    page_config = {}
                else:
                    page_config = _normalize_yaml_values(loaded or {})
                markdown_data = parts[2]
        except (IndexError, yaml.YAMLError) as e:
            print(f"Error parsing YAML frontmatter in {filepath}: {e}")
            page_config = {}
            markdown_data = file_content
    else:
        page_config = {}
        markdown_data = file_content

    page_config["_rel_path"] = rel_path

    if "tags" in page_config:
        page_config["tags"] = list(dict.fromkeys(
            _safe_tag_slug(t)
            for t in _ensure_sequence(page_config.get("tags"))
            if str(t).strip()
        ))

    if md is None:
        md = build_markdown(pygments_theme, markdown_config)
    md.reset()
    html_data = md.convert(markdown_data)
    html_data = _render_callouts(html_data)

    page_config["toc"] = getattr(md, "toc", "")
    page_config["toc_tokens"] = _clean_toc_tokens(getattr(md, "toc_tokens", []))

    plain_text = _strip_html(html_data)
    word_count = len(plain_text.split())
    page_config.setdefault("word_count", word_count)
    page_config.setdefault("reading_time", max(1, round(word_count / 200)))

    first_p = re.search(r"<p(?:\s[^>]*)?>(.*?)</p>", html_data, re.DOTALL)
    p_text = _strip_html(first_p.group(1)) if first_p else plain_text
    excerpt = (p_text[:157].rstrip() + "...") if len(p_text) > 160 else p_text
    page_config.setdefault("excerpt", excerpt)
    if not page_config.get("description") and not page_config.get("summary"):
        page_config["description"] = excerpt

    if not page_config.get("title"):
        toks = page_config["toc_tokens"]
        first_h = toks[0]["name"].strip() if (toks and toks[0].get("level") == 1) else ""
        if first_h:
            html_data = re.sub(r"^\s*<h1[^>]*>.*?</h1>\s*", "", html_data, count=1, flags=re.DOTALL)
            page_config["toc_tokens"] = (toks[0].get("children") or []) + toks[1:]
        stem = os.path.splitext(os.path.basename(filepath))[0]
        if stem == "index" and "/" in rel_path:
            stem = os.path.basename(os.path.dirname(rel_path))
        page_config["title"] = first_h or stem.replace("-", " ").replace("_", " ").title()

    if not page_config.get("layout"):
        md_cfg = markdown_config if isinstance(markdown_config, dict) else {}
        section = rel_path.split("/", 1)[0] if "/" in rel_path else ""
        layouts = {"posts": "post", "docs": "docs", **(md_cfg.get("default_layouts") or {})}
        page_config["layout"] = layouts.get(section) or md_cfg.get("default_layout") or "page"

    raw_url = page_config.get("permalink") if "permalink" in page_config else page_config.get("url")
    custom_url_applied = False
    if raw_url is not None:
        custom_url = os.path.normpath(str(raw_url).strip().lstrip("/\\")).replace("\\", "/")
        if custom_url.endswith(".html"):
            custom_url = custom_url[:-5]
        if custom_url.endswith("/index"):
            custom_url = custom_url[:-6]
        if custom_url in ("", ".", "index"):
            page_config["url"] = "/"
            custom_url_applied = True
        elif not custom_url.startswith("..") and custom_url.split("/")[0] not in PRESERVED_ROOTS and custom_url.split("/")[0] != "tags":
            page_config["url"] = "/" + custom_url.strip("/")
            custom_url_applied = True

    if not custom_url_applied:
        if rel_path.startswith(".."):
            slug = os.path.splitext(os.path.basename(filepath))[0]
            url_path = slug
        else:
            url_path = os.path.splitext(rel_path)[0]

        url_path = url_path.replace(os.sep, "/")

        if url_path == "index":
            page_config["url"] = "/"
        elif url_path.endswith("/index"):
            page_config["url"] = "/" + url_path[:-5]
        else:
            page_config["url"] = "/" + url_path

    # Normalize date to YYYY-MM-DD string
    if "date" in page_config and page_config["date"]:
        parsed_date = safe_parse_date(page_config["date"])
        if parsed_date:
            page_config["date"] = parsed_date.strftime("%Y-%m-%d")
        else:
            page_config["date"] = None

    page_config["content_html"] = html_data

    if page_cache is not None and st is not None:
        page_cache[rel_path] = {
            "mtime_ns": st.st_mtime_ns,
            "size": st.st_size,
            "config_hash": config_hash,
            "page_data": dict(page_config),
            "html_content": html_data,
        }

    return page_config, html_data


def _safe_order(val, default=999):
    try:
        return float(val) if val is not None else default
    except (ValueError, TypeError):
        return default


def build_docs_navigation(docs_pages):
    if not docs_pages:
        return [], []

    for page in docs_pages:
        rel = page.get("_rel_path", "").removeprefix("docs/")
        default_sec = rel.split("/", 1)[0].replace("-", " ").replace("_", " ").title() if "/" in rel else "Overview"
        page["section"] = str(page.get("section") or "").strip() or default_sec

    def _doc_sort_key(page):
        is_root = page.get("url") in ("/docs", "/docs/") or page.get("_rel_path") == "docs/index.md"
        return (_safe_order(page.get("order"), 0 if is_root else 999), page.get("title", "").lower(), page.get("url", ""))

    sections = defaultdict(list)
    for page in docs_pages:
        sections[page["section"]].append(page)

    for sec_title in sections:
        sections[sec_title].sort(key=_doc_sort_key)

    def _section_sort_key(sec_title):
        if sec_title == "Overview":
            return (-1, "")
        items = sections[sec_title]
        min_order = min(_doc_sort_key(p)[0] for p in items) if items else 999
        return (min_order, sec_title.lower())

    sorted_sec_titles = sorted(sections.keys(), key=_section_sort_key)
    docs_tree = [{"title": st, "items": sections[st]} for st in sorted_sec_titles]
    ordered_docs = [item for sec in docs_tree for item in sec["items"]]

    def _nav_link(p):
        return {"title": p.get("title", ""), "url": p.get("url", ""), "section": p.get("section", "")}

    for i, doc in enumerate(ordered_docs):
        doc["prev_page"] = _nav_link(ordered_docs[i - 1]) if i > 0 else None
        doc["next_page"] = _nav_link(ordered_docs[i + 1]) if i + 1 < len(ordered_docs) else None
        crumbs = [{"name": "Docs", "url": "/docs/"}]
        if doc.get("section") and doc["section"] != "Overview":
            crumbs.append({"name": doc["section"], "url": None})
        if doc.get("url") not in ("/docs", "/docs/"):
            crumbs.append({"name": doc.get("title", ""), "url": doc.get("url")})
        doc["breadcrumbs"] = crumbs

    return docs_tree, ordered_docs


def tag_pages(tag_template, site_config, tags=None, image_manifest=None):
    tags = tags or {}
    tags_dir = os.path.join(OUTPUT_DIR, "tags")

    if os.path.isdir(tags_dir):
        for fname in os.listdir(tags_dir):
            if fname.endswith(".html") and fname[:-5] not in tags:
                try:
                    os.remove(os.path.join(tags_dir, fname))
                except OSError:
                    pass

    for tag_name, posts_with_tag in tags.items():
        posts_with_tag.sort(
            key=lambda x: (
                safe_parse_date(x.get("date")) or datetime.min
            ),
            reverse=True
        )
        tag_page_html = tag_template.render(
            site=site_config,
            tag_name=tag_name,
            posts=posts_with_tag,
            page={"title": f"Tag: {tag_name}"},
        )
        tag_page_html = replace_images_with_processed(tag_page_html, image_manifest)
        output_path = os.path.join(tags_dir, f"{tag_name}.html")
        if _write_if_changed(output_path, tag_page_html):
            print(f"Generated tag page: tags/{tag_name}.html")


def render_page(
    page_config,
    html_data,
    site_config,
    templates,
    image_manifest=None,
    **context_data,
):
    layout = page_config.get("layout") or "post"
    if layout == "page" and layout not in templates and "post" in templates:
        layout = "post"
    if layout not in templates:
        available = ", ".join(sorted(templates.keys())) or "none"
        print(
            f"Error: Template '{layout}' not found. Available templates: {available}. Skipping build."
        )
        return

    template = templates[layout]

    render_details = {"site": site_config, "page": page_config, "content": html_data}
    render_details.update(context_data)

    final_html = template.render(render_details)
    final_html = replace_images_with_processed(final_html, image_manifest)

    if page_config["url"] == "/":
        output_path = os.path.join(OUTPUT_DIR, "index.html")
    else:
        output_path = os.path.join(
            OUTPUT_DIR, page_config["url"].lstrip("/"), "index.html"
        )

    if _write_if_changed(output_path, final_html):
        print(
            f"Generated: {page_config['url'] if page_config['url'] != '/' else '/index.html'}"
        )



def load_image_manifest(path=IMAGE_MANIFEST_PATH):
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as exc:
        print(f"Warning: Unable to parse image manifest {path}: {exc}")
        return {}


def _render_attributes(attrs):
    parts = []
    for name, value in attrs:
        if value is None:
            parts.append(f" {name}")
        else:
            parts.append(f' {name}="{escape(str(value), quote=True)}"')
    return "".join(parts)


def _build_picture_element(attrs, manifest_entry):
    if not manifest_entry:
        return None

    attrs_dict = {name.lower(): value for name, value in attrs}
    sizes_value = attrs_dict.get("data-img-sizes") or attrs_dict.get("sizes") or "100vw"

    format_priority = ["avif", "webp", "jpg", "jpeg", "png"]
    fallback_priority = ["jpg", "jpeg", "png", "webp", "avif"]
    mime_overrides = {"jpg": "image/jpeg", "jpeg": "image/jpeg"}

    sources = []
    for fmt in format_priority:
        variants = manifest_entry.get(fmt)
        if not variants:
            continue
        sorted_variants = sorted(
            (v for v in variants if v.get("path") and v.get("width")),
            key=lambda item: item["width"],
        )
        if not sorted_variants:
            continue
        srcset = ", ".join(
            f"{variant['path'] if variant['path'].startswith('http') else '/' + variant['path']} {variant['width']}w"
            for variant in sorted_variants
        )
        mime = mime_overrides.get(fmt, f"image/{fmt}")
        sources.append(
            f'<source type="{mime}" srcset="{srcset}" sizes="{sizes_value}">'
        )

    if not sources:
        return None

    fallback_format = next(
        (fmt for fmt in fallback_priority if manifest_entry.get(fmt)), None
    )
    if not fallback_format:
        return None

    fallback_variants = sorted(
        (
            v
            for v in manifest_entry[fallback_format]
            if v.get("path") and v.get("width")
        ),
        key=lambda item: item.get("width", 0),
    )
    if not fallback_variants:
        return None

    if fallback_variants[-1]['path'].startswith("http"):
        fallback_src = fallback_variants[-1]['path']
    else:
        fallback_src = f"/{fallback_variants[-1]['path']}"

    fallback_srcset = ", ".join(
        f"{variant['path'] if variant['path'].startswith('http') else '/' + variant['path']} {variant['width']}w" 
        for variant in fallback_variants
    )

    filtered_attrs = [
        (name, value)
        for (name, value) in attrs
        if name.lower() not in {"src", "srcset", "sizes", "data-img-sizes"}
    ]
    fallback_attrs = [("src", fallback_src)] + filtered_attrs
    if fallback_srcset:
        fallback_attrs.append(("srcset", fallback_srcset))
    fallback_attrs.append(("sizes", sizes_value))

    img_tag = "<img{}>".format(_render_attributes(fallback_attrs))
    sources_html = "".join(sources)
    return f"<picture>{sources_html}{img_tag}</picture>"


class ImageReplacementParser(HTMLParser):
    def __init__(self, manifest):
        super().__init__(convert_charrefs=False)
        self.manifest = manifest or {}
        self.output = []
        self.picture_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() == "picture":
            self.picture_depth += 1
        self._handle_start(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._handle_start(tag, attrs)

    def handle_endtag(self, tag):
        if tag.lower() == "picture" and self.picture_depth > 0:
            self.picture_depth -= 1
        self.output.append(f"</{tag}>")

    def handle_data(self, data):
        self.output.append(data)

    def handle_comment(self, data):
        self.output.append(f"<!--{data}-->")

    def handle_decl(self, decl):
        self.output.append(f"<!{decl}>")

    def handle_entityref(self, name):
        self.output.append(f"&{name};")

    def handle_charref(self, name):
        self.output.append(f"&#{name};")

    def handle_pi(self, data):
        self.output.append(f"<?{data}>")

    def _handle_start(self, tag, attrs):
        if tag.lower() == "img" and self.picture_depth == 0:
            replacement = self._build_replacement(attrs)
            if replacement:
                self.output.append(replacement)
                return
        raw = self.get_starttag_text()
        if raw:
            self.output.append(raw)

    def _build_replacement(self, attrs):
        attrs_dict = {k.lower(): v for k, v in attrs}
        src = attrs_dict.get("src")
        if not src:
            return None

        if src.startswith(("http://", "https://", "//", "data:")):
            return None

        normalized = src.split("?", 1)[0].split("#", 1)[0].lstrip("/")
        if normalized.startswith("./"):
            normalized = normalized[2:]
        if "assets/images/" not in normalized:
            return None

        relative = normalized.split("assets/images/", 1)[1].replace("\\", "/")
        manifest_entry = self.manifest.get(relative)
        if not manifest_entry:
            return None

        return _build_picture_element(attrs, manifest_entry)

    def get_html(self):
        return "".join(self.output)


def replace_images_with_processed(html, manifest):
    if not html or not manifest:
        return html
    parser = ImageReplacementParser(manifest)
    parser.feed(html)
    parser.close()
    return parser.get_html()


def generate_feeds(collections, site_config, env):
    build_time = datetime.now(timezone.utc).isoformat()
    site_name = site_config.get("site_name", "Site")
    author = site_config.get("author", "")

    # Load feeds configuration
    feeds_config = site_config.get("feeds")
    if not isinstance(feeds_config, list):
        # Default feeds matching sibling repo behavior
        feeds_config = [
            {
                "filename": "feed.xml",
                "layouts": ["post", "til"],
                "title": site_name,
                "subtitle": f"All posts and TILs from {author}",
                "content": False
            },
            {
                "filename": "blog/feed.xml",
                "layouts": ["post"],
                "title": f"{site_name} - Blog",
                "subtitle": f"Blog posts from {author}",
                "content": False
            },
            {
                "filename": "til/feed.xml",
                "layouts": ["til"],
                "title": f"{site_name} - TIL",
                "subtitle": f"Today I Learned posts from {author}",
                "content": False
            }
        ]

    try:
        feed_tmpl = env.get_template("feed.xml.j2")
    except Exception as e:
        print(f"Warning: feed.xml.j2 template not found. Skipping feed generation. Error: {e}")
        return

    def _pages_to_feed_entries(layout_names, include_content=False):
        entries = []
        for layout_name in layout_names:
            for page in collections.get(layout_name, []):
                if str(page.get("feed", "true")).lower() in ("false", "0", "no"):
                    continue
                if not page.get("date"):
                    continue
                parsed_date = safe_parse_date(page.get("date"))
                if parsed_date:
                    if parsed_date.tzinfo is None:
                        parsed_date = parsed_date.replace(tzinfo=timezone.utc)
                    date_iso = parsed_date.isoformat()
                else:
                    date_iso = datetime.now(timezone.utc).isoformat()

                # Fetch full html if configured
                content_html = page.get("content_html", "") if include_content else ""

                entries.append({
                    "title": page.get("title", "Untitled"),
                    "url": page.get("url", "/"),
                    "date_iso": date_iso,
                    "tags": page.get("tags") or [],
                    "description": page.get("description") or page.get("summary") or "",
                    "content_html": content_html,
                    "layout": layout_name,
                })
        entries.sort(key=lambda x: x["date_iso"], reverse=True)
        return entries

    for feed_cfg in feeds_config:
        if not isinstance(feed_cfg, dict):
            continue
        filename = feed_cfg.get("filename")
        if not filename:
            continue

        layouts = _ensure_sequence(feed_cfg.get("layouts"))
        if not layouts:
            continue

        title = feed_cfg.get("title") or site_name
        subtitle = feed_cfg.get("subtitle") or f"Posts from {author}"
        include_content = bool(feed_cfg.get("content", False))

        entries = _pages_to_feed_entries(layouts, include_content=include_content)

        clean_rel = os.path.normpath(str(filename).lstrip("/\\")).replace("\\", "/")
        if clean_rel.startswith("..") or clean_rel.split("/")[0] in PRESERVED_ROOTS:
            print(f"Warning: Skipping unsafe feed filename: {filename}")
            continue
        out_path = os.path.join(OUTPUT_DIR, clean_rel)

        feed_updated = entries[0]["date_iso"] if entries else "1970-01-01T00:00:00+00:00"

        try:
            rendered = feed_tmpl.render(
                site=site_config,
                feed_entries=entries,
                feed_title=title,
                feed_subtitle=subtitle,
                feed_self_url="/" + clean_rel.lstrip("/"),
                feed_alt_url="/",
                build_time=feed_updated,
            )
            if _write_if_changed(out_path, rendered):
                print(f"Generated feed: {filename} ({len(entries)} entries)")
        except Exception as e:
            print(f"Error: Failed to generate feed {filename}: {e}")


def scaffold_content(title, kind="post", content_dir=CONTENT_DIR):
    title = str(title or "").strip()
    kind = str(kind or "post").strip().lower()
    for prefix, k in (("docs/", "doc"), ("posts/", "post")):
        if title.lower().startswith(prefix):
            kind, title = k, title[len(prefix):].strip()
            break
    if not title:
        print("Error: Title cannot be empty.")
        sys.exit(1)

    slug = "/".join(
        s for p in title.lower().split("/")
        if p not in ("", ".", "..") and (s := re.sub(r"[^a-z0-9]+", "-", p).strip("-"))
    ) or "untitled"
    subdirs = {"post": "posts", "doc": "docs", "page": ""}
    kind = kind if kind in subdirs else "post"
    target_path = os.path.join(content_dir, subdirs[kind], f"{slug}.md")
    if os.path.exists(target_path):
        print(f"Error: File already exists: {target_path}")
        sys.exit(1)

    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
    q_title = json.dumps(title)
    today = datetime.now().strftime("%Y-%m-%d")
    frontmatter = {
        "post": f'title: {q_title}\ndate: "{today}"\nlayout: "post"\ntags: []',
        "doc": f'title: {q_title}\nlayout: "docs"\norder: 10',
        "page": f'title: {q_title}\nlayout: "page"',
    }[kind]
    with open(target_path, "w", encoding="utf-8") as f:
        f.write(f"---\n{frontmatter}\n---\n\nWrite your {kind} content here.\n")
    print(f"Created {kind}: {target_path}")
    return target_path


def check_site(
    config_path=CONFIG_FILE,
    content_dir=CONTENT_DIR,
    template_dir=TEMPLATE_DIR,
    images_dir=IMAGES_DIR,
    exit_on_error=False,
):
    errors = []
    warnings = []

    config = {}
    if not os.path.exists(config_path):
        errors.append(f"Config file not found: {config_path}")
    else:
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                loaded = yaml.safe_load(f)
                if isinstance(loaded, dict):
                    config = loaded
                    if not config.get("site_name"):
                        warnings.append(f"Missing 'site_name' in {config_path}")
                    if not config.get("base_url"):
                        warnings.append(f"Missing 'base_url' in {config_path}")
                else:
                    errors.append(f"Config file {config_path} is not a valid YAML dictionary")
        except (OSError, yaml.YAMLError) as e:
            errors.append(f"Invalid YAML in {config_path}: {e}")

    env = Environment(
        loader=FileSystemLoader(template_dir) if os.path.isdir(template_dir) else FileSystemLoader("."),
        autoescape=select_autoescape(["html", "htm", "xml", "j2"]),
    )
    try:
        templates = load_templates(env, template_dir=template_dir) if os.path.isdir(template_dir) else {}
    except Exception as e:
        errors.append(f"Template error: {e}")
        templates = {}

    pygments_theme = resolve_pygments_theme(config)
    md_config = dict(config.get("markdown") or {})
    for k in ("default_layout", "default_layouts"):
        if k not in md_config and config.get(k):
            md_config[k] = config[k]
    md = build_markdown(pygments_theme, md_config)

    seen_urls = {}
    if not os.path.isdir(content_dir):
        warnings.append(f"Content directory not found: {content_dir}")
    else:
        for root, _, files in os.walk(content_dir):
            for filename in files:
                if not filename.endswith(".md"):
                    continue
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, content_dir).replace(os.sep, "/")

                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        raw = f.read()
                    if raw.startswith("---"):
                        parts = raw.split("---", 2)
                        if len(parts) < 3:
                            errors.append(f"Unclosed frontmatter in {rel_path}")
                            continue
                        else:
                            try:
                                fm = yaml.safe_load(parts[1])
                                if fm is not None and not isinstance(fm, dict):
                                    errors.append(f"Frontmatter in {rel_path} must be a dictionary, got {type(fm).__name__}")
                                    continue
                            except yaml.YAMLError as ye:
                                errors.append(f"Invalid YAML frontmatter in {rel_path}: {ye}")
                                continue
                except OSError as e:
                    errors.append(f"Could not read {rel_path}: {e}")
                    continue

                page_data, html_content = parse_file(
                    filepath,
                    pygments_theme,
                    md_config,
                    md=md,
                    content_dir=content_dir,
                )
                if not page_data:
                    continue

                layout = page_data.get("layout") or "post"
                effective_layout = "post" if (layout == "page" and layout not in templates and "post" in templates) else layout

                if templates and effective_layout not in templates:
                    errors.append(f"Missing template '{layout}' for {rel_path}")

                if str(page_data.get("draft")).lower() not in ("true", "1", "yes"):
                    url = page_data.get("url")
                    if url in seen_urls:
                        errors.append(f"Duplicate URL '{url}' in {rel_path} and {seen_urls[url]}")
                    else:
                        seen_urls[url] = rel_path

                hero = page_data.get("hero_image")
                candidates = ([hero] if isinstance(hero, str) else []) + re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html_content or "")
                images_to_check = [s for s in candidates if "assets/images/" in s and not s.startswith(("http://", "https://", "//", "data:"))]
                for img_ref in images_to_check:
                    clean_ref = img_ref.split("?", 1)[0].split("#", 1)[0]
                    rel_img = clean_ref.split("assets/images/", 1)[1].lstrip("/")
                    if not os.path.exists(os.path.join(images_dir, rel_img)):
                        warnings.append(f"Referenced image not found: {img_ref} in {rel_path}")

    for w in warnings:
        print(f"Warning: {w}")
    for e in errors:
        print(f"Error: {e}")

    if errors:
        print(f"Site check failed with {len(errors)} error(s).")
        if exit_on_error:
            sys.exit(1)
    else:
        print("Site check passed.")

    return errors, warnings


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--generate-styles", action="store_true")
    parser.add_argument("--new", nargs="?", const="", metavar="TITLE", help="Scaffold a new markdown file")
    parser.add_argument("title", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("--kind", choices=["post", "page", "doc"], default="post", help="Kind of content to scaffold")
    parser.add_argument("--check", action="store_true", help="Validate site configuration and content")
    args = parser.parse_args()

    if args.new is not None:
        scaffold_content(args.new or args.title, kind=args.kind)
        return

    if args.check:
        check_site(exit_on_error=True)
        return

    if args.clean:
        clean_output(OUTPUT_DIR)
        if os.path.exists(PAGE_SLUG_CACHE):
            os.remove(PAGE_SLUG_CACHE)
        print("generated files are deleted.")
        return

    if args.generate_styles:
        _, syntax_theme = generate_styles()
        print(
            f"Generated theme, font, and syntax CSS (Pygments theme: {syntax_theme})."
        )
        return

    site_config, pygments_theme = generate_styles()
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=select_autoescape(["html", "htm", "xml", "j2"]),
    )
    templates = load_templates(env)
    image_manifest = load_image_manifest()
    page_cache = load_page_cache()
    md_config = dict(site_config.get("markdown") or {})
    for k in ("default_layout", "default_layouts"):
        if k not in md_config and site_config.get(k):
            md_config[k] = site_config[k]
    config_hash = json.dumps(
        {"theme": pygments_theme, "md": md_config},
        sort_keys=True,
        default=str,
    )
    md = build_markdown(pygments_theme, md_config)

    if args.file:
        print(f"Change detected in {args.file}, proceeding to rebuild...")
    else:
        print("Running a full build...")
        clean_output(OUTPUT_DIR)

    sitemap_list = []
    pages = []
    tags = {}

    current_slugs = set()
    previous_slugs = load_previous_slugs()

    collections = defaultdict(list)
    seen_rel_paths = set()

    for root, _, files in os.walk(CONTENT_DIR):
        for filename in files:
            if not filename.endswith(".md"):
                continue
            
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, CONTENT_DIR).replace(os.sep, "/")
            seen_rel_paths.add(rel_path)

            page_data, html_content = parse_file(
                filepath,
                pygments_theme,
                md_config,
                md=md,
                page_cache=page_cache,
                config_hash=config_hash,
            )
            if not page_data:
                continue
            if str(page_data.get("draft")).lower() in ("true", "1", "yes"):
                continue
            
            slug_key = page_data["url"].lstrip("/") or "index"
            current_slugs.add(slug_key)

            pages.append({"data": page_data, "content": html_content})

            lastmod = page_data.get("date")
            if not lastmod:
                try:
                    lastmod = datetime.fromtimestamp(os.path.getmtime(filepath)).strftime("%Y-%m-%d")
                except OSError:
                    lastmod = datetime.now().strftime("%Y-%m-%d")
            sitemap_list.append({"url": page_data["url"], "lastmod": lastmod})
            
            layout = page_data.get("layout")
            if layout:
                collections[layout].append(page_data)
                
            for tag in page_data.get("tags") or []:
                tags.setdefault(tag, []).append(page_data)

    removed = previous_slugs - current_slugs
    for slug in removed:
         if slug == "index":
             index_path = os.path.join(OUTPUT_DIR, "index.html")
             if os.path.isfile(index_path):
                 os.remove(index_path)
                 print(f"Removed deleted page output: {index_path}")
             continue
         top_level = slug.lstrip("/").split("/")[0]
         if not top_level or top_level in PRESERVED_ROOTS:
             continue
         out_path = os.path.join(OUTPUT_DIR, slug)
         if os.path.isdir(out_path):
             shutil.rmtree(out_path, ignore_errors=True)
             print(f"Removed stale page directory: {out_path}")
         elif os.path.isfile(out_path):
             os.remove(out_path)
             print(f"Removed stale page file: {out_path}")

    for k in set(page_cache) - seen_rel_paths:
        del page_cache[k]

    save_current_slugs(current_slugs)
    save_page_cache(page_cache)

    for layout_name, items in collections.items():
        if not items:
            continue
        
        has_date = any(x.get("date") for x in items)
        has_order = any(x.get("order") is not None for x in items)
        
        if has_date:
            items.sort(
                key=lambda x: (
                    safe_parse_date(x.get("date")) or datetime.min
                ),
                reverse=True,
            )
        elif has_order:
            items.sort(key=lambda x: _safe_order(x.get("order"), 999))

    docs_tree, ordered_docs = build_docs_navigation(collections.get("docs", []))
    if ordered_docs:
        collections["docs"] = ordered_docs

    context_data = {f"{k.replace('-', '_')}s": v for k, v in collections.items()}
    context_data["all_tags"] = tags
    context_data["docs_tree"] = docs_tree
    context_data["docs"] = ordered_docs

    for page in pages:
        render_page(
            page["data"],
            page["content"],
            site_config,
            templates,
            image_manifest=image_manifest,
            **context_data
        )

    search_index = [
        {
            "title": p["data"].get("title", ""),
            "url": p["data"]["url"] if p["data"]["url"].endswith("/") else p["data"]["url"] + "/",
            "section": p["data"].get("section", ""),
            "layout": p["data"].get("layout", ""),
            "tags": p["data"].get("tags") or [],
            "headings": _flatten_toc_headings(p["data"].get("toc_tokens")),
            "excerpt": p["data"].get("description") or p["data"].get("excerpt", ""),
        }
        for p in pages
    ]
    _write_if_changed(os.path.join(OUTPUT_DIR, "search-index.json"), json.dumps(search_index, ensure_ascii=False))

    tag_template = templates.get("tags") or templates.get("tags.html")
    if tag_template:
        tag_pages(
            tag_template,
            site_config,
            tags,
            image_manifest=image_manifest,
        )
    else:
        print("Warning: tags template not found; skipping tag page generation.")

    sitemap_template = env.get_template("sitemap.xml.j2")
    sitemap_xml = sitemap_template.render(site=site_config, pages=sitemap_list)
    if _write_if_changed(os.path.join(OUTPUT_DIR, "sitemap.xml"), sitemap_xml):
        print("Generated sitemap.xml")

    # Generate RSS/Atom feeds
    generate_feeds(collections, site_config, env)


if __name__ == "__main__":
    main()
