# mettu - a Static Site Generator using Python and Vite

**mettu** (మెట్లు, /ˈmɛt.t̪u/) is a simple, flexible, high-performance static site generator that combines Python for backend processing (Markdown, YAML frontmatter, Pygments, Jinja2) and Vite for frontend development (Tailwind CSS v4 and DaisyUI v5).

It is built for personal blogs, portfolio sites, and first-class **documentation portals** with client-side search, callouts, and automatic navigation.

---

## Why the name?
"mettu" is a Telugu word meaning a *stair* or *step*. It represents a step towards building your own tools, and conveniently, a step towards publishing your website!

---

## Features

- ⚡ **Hybrid Architecture**: Fast Python engine for Markdown parsing, syntax highlighting, and feed generation + Vite for Tailwind CSS v4, DaisyUI v5, and HMR.
- 🚀 **High Performance**: In-memory and disk caching for Markdown ASTs, dependency hash tracking to skip redundant `pip install` checks, and sub-300ms builds.
- 📚 **First-Class Documentation Sites**:
  - Dedicated 3-column documentation layout with sticky on-page Table of Contents.
  - Automatic hierarchical sidebar tree with section grouping and `order:` sorting.
  - Sequential **Previous / Next** pagination links and breadcrumb trails.
  - Built-in `⌘K` / `Ctrl+K` client-side instant search modal (`/search-index.json`).
  - GitHub-style callouts (`> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`).
  - One-click **Copy** button on all code blocks.
- ✍️ **Zero-Boilerplate Content Authoring**:
  - Optional frontmatter: automatic title inference from `# Heading` or filename stem.
  - Directory-based default layout inference (`posts/` → `post`, `docs/` → `docs`, others → `page`).
  - Automated reading time calculation and plain-text excerpt generation.
  - Custom `permalink` overrides for fine-grained URL routing.
  - Universal tagging across all content pages with dedicated tag index pages.
- 🎨 **Theming & Design**:
  - DaisyUI v5 presets and custom CSS color definitions.
  - Built-in navbar theme switcher with pre-paint `localStorage` persistence.
  - Pygments code syntax highlighting with auto-generated stylesheet.
- 🖼️ **Responsive Image Optimization**:
  - Automatic WebP, AVIF, and JPEG generation at multiple breakpoints via Sharp.
  - Automatic markup rewrite into responsive `<picture>` elements with `srcset`.
  - Optional remote upload and sync with S3/Backblaze B2 buckets.
- 📡 **Web Feeds & SEO**:
  - Automatic Atom/RSS feed generation with human-readable styling (`pretty-feed-v3.xsl`).
  - XML sitemap (`/sitemap.xml`) generation with valid `<loc>` and `<lastmod>` timestamps.
  - OpenGraph and meta description tags.
- 🛠️ **Developer Experience (DX)**:
  - Scaffolding CLI: `npm run new -- "My New Post"`.
  - Site health & link validator: `npm run check`.
  - Zero-dependency unit test suite: `npm test`.

---

## Requirements

- **Python**: 3.9+
- **Node.js**: 18+ and npm
- **Vite**, **Tailwind CSS v4**, and **DaisyUI v5** (managed via npm)

---

## Quick Start

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Andy34G7/mettu.git
   cd mettu
   ```

2. **Install dependencies**:
   ```bash
   npm install
   ```
   *Note: Python dependencies (`Markdown`, `Jinja2`, `PyYAML`, `Pygments`, `python-dotenv`) are automatically installed into a local `.venv` on first run.*

3. **Start the development server**:
   ```bash
   npm run dev
   ```
   Open `http://localhost:5173` in your browser. Changes to Markdown files, templates, or styles update live via Vite's HMR.

4. **Build for production**:
   ```bash
   npm run build
   ```
   The fully bundled, self-contained static site will be written to `./dist`.

---

## CLI Commands

| Command | Description |
| :--- | :--- |
| `npm run dev` | Starts the Vite dev server with live reloading and Python build watcher. |
| `npm run build` | Compiles pages, feeds, sitemaps, search indices, and assets into `./dist`. |
| `npm run preview` | Serves the production `./dist` directory locally to test before deployment. |
| `npm run new -- "<Title>"` | Scaffolds a new post, doc, or page with starter frontmatter. |
| `npm run check` | Validates configuration, frontmatter syntax, layouts, URLs, and image links. |
| `npm test` | Runs the automated Python unit test suite (`tests/test_ssg.py`). |
| `npm run clean` | Cleans temporary build artifacts and caches. |

### Scaffolding Content (`npm run new`)

Quickly scaffold new content with safe URL slugs and boilerplate frontmatter:

```bash
# Scaffold a blog post in content/posts/my-new-post.md
npm run new -- "My New Post"

# Scaffold a documentation page in content/docs/api-guide.md
npm run new -- --kind doc "API Guide"
# Or prefix with docs/
npm run new -- "docs/api-guide"

# Scaffold a general standalone page in content/about.md
npm run new -- --kind page "About"
```

---

## Configuration (`config.yaml`)

Configure site-wide settings in `config.yaml`:

```yaml
site_name: "My Site"
author: "Your Name"
base_url: "https://example.com"
base_path: "" # Optional path prefix, e.g. "/subsite"

runtime:
  python_executable: "python3" # Optional; defaults to .venv or system python

theme:
  default: "cupcake" # Active theme
  include: # Themes included in the switcher
    - "cupcake"
    - "dracula"
  custom:
    mytheme:
      primary: "#570df8"
      secondary: "#f000b8"
      accent: "#37cdbe"

fonts:
  imports:
    - "https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Space+Grotesk:wght@500;700&display=swap"
  families:
    body: "'Inter', sans-serif"
    heading: "'Space Grotesk', sans-serif"
    mono: "'JetBrains Mono', monospace"

syntax:
  pygments_theme: "dracula" # Controls syntax highlighting theme

markdown:
  default_layout: "page"
  default_layouts:
    posts: "post"
    docs: "docs"
  extensions:
    - fenced_code
    - codehilite
    - footnotes
    - tables
    - attr_list
    - sane_lists
    - md_in_html
    - nl2br
    - toc:
        permalink: true

images:
  formats:
    - webp
    - jpg

navigation:
  - name: "Home"
    url: "/"
  - name: "Blog"
    url: "/blog/"
  - name: "Docs"
    url: "/docs/"

feeds:
  - filename: "feed.xml"
    layouts: ["post"]
    title: "My Site Feed"
    subtitle: "Thoughts and findings"
    content: true
```

---

## Content Authoring

Create Markdown (`.md`) files in the `content/` directory.

### Frontmatter Reference

All frontmatter is optional. Sensible defaults are inferred whenever fields are omitted:

```yaml
---
title: "Understanding Architecture"       # Inferred from first # Heading or filename if omitted
layout: "post"                            # Inferred by folder: posts/ -> post, docs/ -> docs, else -> page
date: "2026-11-10"                        # Publication date (YYYY-MM-DD)
tags:                                     # List or single string; normalized safely to URL slugs
  - "architecture"
  - "web-dev"
permalink: "/articles/architecture/"      # Optional custom route override
show_toc: true                            # Displays collapsible on-page Table of Contents
description: "A deep dive into system..." # Inferred from the first paragraph if omitted
draft: false                              # Set to true to exclude from builds and feeds
---

Content goes here...
```

### GitHub-Style Callouts

Write GitHub-style admonitions inside blockquotes. They automatically transform into DaisyUI alert elements:

```markdown
> [!NOTE]
> Useful background context or general information.

> [!TIP]
> Pro-tips or performance suggestions.

> [!IMPORTANT]
> Key requirements or crucial information.

> [!WARNING]
> Warnings and potential breaking changes.

> [!CAUTION]
> High-risk actions that could cause data loss or security issues.
```

---

## Documentation Sites (`layout: "docs"`)

`mettu` provides complete documentation site generation out of the box. Any file placed under `content/docs/` automatically receives the `docs` layout.

### Organization & Sectioning

Organize documentation files into folders or assign sections via frontmatter:

```
content/docs/
├── index.md                 # Overview (order: 1)
├── getting-started.md       # Overview (order: 2)
└── guide/
    ├── configuration.md     # Section: Guide (order: 3)
    └── authoring.md         # Section: Guide (order: 4)
```

Or specify in frontmatter:

```yaml
---
title: "Configuration"
section: "Advanced Guide"
order: 3
---
```

### Docs Features
- **Sidebar Navigation Tree**: Automatically groups pages by `section` (with `"Overview"` first), ordered by `order:` and title.
- **Previous & Next Links**: Sequential bottom pagination linking the reader through the documentation flow.
- **Breadcrumbs**: Automatically generated breadcrumb hierarchy.
- **On-Page TOC**: Sticky right-hand navigation for `h2` and `h3` headings.
- **Instant Search (`⌘K` / `Ctrl+K`)**: Fast client-side modal filtering through titles, sections, headings, tags, and excerpts.
- **Code Copy**: Every code block features an automatic one-click **Copy** button.

---

## Image Optimization & S3 Storage

1. Place source images into `assets/images/`.
2. When building or developing, Sharp automatically resizes images to responsive widths (e.g. 640px, 1280px, 1920px) and converts them into modern formats (`.webp`, `.jpg`).
3. Local `<img src="/assets/images/example.png">` references are automatically converted into `<picture>` elements with responsive `srcset` definitions.

### Optional S3 / Backblaze B2 Upload

To host processed images on an S3-compatible bucket:

1. Copy the environment template:
   ```bash
   cp .env.example .env
   ```
2. Configure credentials in `.env`:
   ```env
   S3_BUCKET="my-bucket"
   S3_REGION="us-east-1"
   S3_ENDPOINT="https://s3.us-east-1.amazonaws.com"
   S3_ACCESS_KEY="your-access-key"
   S3_SECRET_KEY="your-secret-key"
   S3_PUBLIC_URL="https://cdn.example.com"
   ```

---

## Web Feeds & Sitemaps

- **Atom/RSS Feeds**: Feeds specified in `config.yaml` are generated with RFC-compliant timestamps, full post content (optional), and styled via `public/pretty-feed-v3.xsl` for direct browser viewing.
- **Excluding from Feeds**: Add `feed: false` to any page's frontmatter.
- **Sitemap**: `/sitemap.xml` is automatically generated with valid URLs and `<lastmod>` timestamps derived from post dates or file modification times.

---

## Site Health Validation (`npm run check`)

Run the built-in validator to inspect site integrity before committing or deploying:

```bash
npm run check
```

Validates:
- Syntax and required keys in `config.yaml`.
- Frontmatter validity across all Markdown files.
- Existence and syntax of referenced layout templates in `templates/`.
- Duplicate URL or permalink collisions.
- Existence of local images referenced in Markdown or frontmatter.

---

## License

This project is licensed under the [ISC License](LICENSE.md).
